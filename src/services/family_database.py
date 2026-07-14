"""Base local para las fichas familiares de Victor Document AI.

La base es independiente de Access y de las carpetas del NAS.  Access se usa
solamente como origen de una importación, por lo que el archivo original nunca
se modifica.
"""

import json
import os
import sqlite3
import subprocess
import shutil
import tempfile
import re
import unicodedata
import uuid
from pathlib import Path


class FamilyDatabase:
    RELATED = {
        "emails": ("Emails", ("email", "type", "primary", "note")),
        "phones": ("Teléfonos", ("phone", "type", "primary", "note")),
        "services": (
            "Servicios y suscripciones",
            ("service_type", "company", "client_number", "contract_number", "username",
             "monthly_price", "billing_day", "payment_method", "start_date", "end_date", "note"),
        ),
        "insurances": (
            "Seguros",
            ("insurance_type", "company", "policy_number", "start_date", "end_date",
             "monthly_payment", "status", "note"),
        ),
        "bank_accounts": (
            "Cuentas bancarias",
            ("bank", "iban", "account_type", "holder", "status", "note"),
        ),
        "cards": ("Tarjetas", ("bank", "card_type", "last_four", "end_date", "status", "note")),
        "documents": (
            "Documentos personales",
            ("document_type", "document_number", "issuing_country", "issue_date", "expiry_date",
             "file_path", "status", "note"),
        ),
        "vehicles": (
            "Vehículos",
            ("brand", "model", "registration", "year", "colour", "vin", "fuel", "apk_until", "status", "note"),
        ),
        "family_relations": ("Relaciones familiares", ("relative_name", "relationship_type", "note")),
    }

    def __init__(self, path=None):
        self.path = Path(path or Path(__file__).resolve().parents[2] / "data" / "family.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._create_schema()

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _create_schema(self):
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS people (
                    id INTEGER PRIMARY KEY,
                    folder_name TEXT UNIQUE NOT NULL,
                    given_names TEXT, surname TEXT, date_of_birth TEXT, tax_number TEXT,
                    reference_notes TEXT, address TEXT, postcode TEXT, city TEXT,
                    country TEXT, note TEXT
                );
                CREATE TABLE IF NOT EXISTS custom_tabs (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL
                );
                CREATE TABLE IF NOT EXISTS custom_entries (
                    id INTEGER PRIMARY KEY,
                    person_id INTEGER NOT NULL,
                    tab_id INTEGER NOT NULL,
                    concept TEXT, detail TEXT, note TEXT,
                    values_json TEXT,
                    FOREIGN KEY(person_id) REFERENCES people(id) ON DELETE CASCADE,
                    FOREIGN KEY(tab_id) REFERENCES custom_tabs(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS person_tab_settings (
                    person_id INTEGER NOT NULL,
                    tab_key TEXT NOT NULL,
                    visible INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY(person_id, tab_key),
                    FOREIGN KEY(person_id) REFERENCES people(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS custom_tab_fields (
                    id INTEGER PRIMARY KEY,
                    tab_id INTEGER NOT NULL,
                    field_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    UNIQUE(tab_id, field_key),
                    FOREIGN KEY(tab_id) REFERENCES custom_tabs(id) ON DELETE CASCADE
                );
                """
            )
            for table, (_, columns) in self.RELATED.items():
                fields = ", ".join(f'"{column}" TEXT' for column in columns)
                db.execute(
                    f"CREATE TABLE IF NOT EXISTS {table} "
                    f"(id INTEGER PRIMARY KEY, person_id INTEGER NOT NULL, {fields}, "
                    "FOREIGN KEY(person_id) REFERENCES people(id) ON DELETE CASCADE)"
                )
            columns = {row[1] for row in db.execute("PRAGMA table_info(custom_entries)")}
            if "values_json" not in columns:
                db.execute("ALTER TABLE custom_entries ADD COLUMN values_json TEXT")
            for tab in db.execute("SELECT id FROM custom_tabs"):
                self._ensure_default_custom_fields(db, tab["id"])

    def sync_folders(self, root):
        root = Path(root)
        if not root.exists():
            return 0
        added = 0
        with self._connect() as db:
            for folder in root.iterdir():
                if not folder.is_dir():
                    continue
                present = db.execute(
                    "SELECT id FROM people WHERE folder_name = ?", (folder.name,)
                ).fetchone()
                if not present:
                    db.execute(
                        "INSERT INTO people (folder_name, given_names) VALUES (?, ?)",
                        (folder.name, folder.name),
                    )
                    added += 1
        return added

    def people(self):
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM people ORDER BY COALESCE(given_names, ''), COALESCE(surname, ''), folder_name"
            )]

    def custom_tabs(self):
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM custom_tabs ORDER BY name COLLATE NOCASE")]

    def add_custom_tab(self, name):
        name = (name or "").strip()
        if not name:
            raise ValueError("Escribe un nombre para la nueva pestaña.")
        with self._connect() as db:
            cursor = db.execute("INSERT INTO custom_tabs (name) VALUES (?)", (name,))
            self._ensure_default_custom_fields(db, cursor.lastrowid)
            return cursor.lastrowid

    def rename_custom_tab(self, tab_id, name):
        name = (name or "").strip()
        if not name:
            raise ValueError("El nombre de la pestaña no puede estar vacío.")
        with self._connect() as db:
            db.execute("UPDATE custom_tabs SET name = ? WHERE id = ?", (name, tab_id))

    def delete_custom_tab(self, tab_id):
        with self._connect() as db:
            db.execute("DELETE FROM custom_entries WHERE tab_id = ?", (tab_id,))
            db.execute("DELETE FROM custom_tab_fields WHERE tab_id = ?", (tab_id,))
            db.execute("DELETE FROM custom_tabs WHERE id = ?", (tab_id,))

    def custom_tab_fields(self, tab_id):
        with self._connect() as db:
            self._ensure_default_custom_fields(db, tab_id)
            return [dict(row) for row in db.execute(
                "SELECT * FROM custom_tab_fields WHERE tab_id = ? ORDER BY position, id", (tab_id,)
            )]

    def add_custom_field(self, tab_id, name):
        name = (name or "").strip()
        if not name:
            raise ValueError("Escribe un nombre para el campo.")
        with self._connect() as db:
            position = db.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM custom_tab_fields WHERE tab_id = ?", (tab_id,)
            ).fetchone()[0]
            field_key = f"field_{uuid.uuid4().hex[:10]}"
            db.execute(
                "INSERT INTO custom_tab_fields (tab_id, field_key, name, position) VALUES (?, ?, ?, ?)",
                (tab_id, field_key, name, position),
            )

    def rename_custom_field(self, field_id, name):
        name = (name or "").strip()
        if not name:
            raise ValueError("El nombre del campo no puede estar vacío.")
        with self._connect() as db:
            db.execute("UPDATE custom_tab_fields SET name = ? WHERE id = ?", (name, field_id))

    def delete_custom_field(self, field_id):
        with self._connect() as db:
            field = db.execute("SELECT tab_id, field_key FROM custom_tab_fields WHERE id = ?", (field_id,)).fetchone()
            if not field:
                return
            for entry in db.execute("SELECT id, values_json FROM custom_entries WHERE tab_id = ?", (field["tab_id"],)):
                values = self._entry_values(entry)
                values.pop(field["field_key"], None)
                db.execute("UPDATE custom_entries SET values_json = ? WHERE id = ?", (json.dumps(values, ensure_ascii=False), entry["id"]))
            db.execute("DELETE FROM custom_tab_fields WHERE id = ?", (field_id,))

    def tab_visible(self, person_id, tab_key):
        with self._connect() as db:
            row = db.execute(
                "SELECT visible FROM person_tab_settings WHERE person_id = ? AND tab_key = ?",
                (person_id, tab_key),
            ).fetchone()
            return bool(row["visible"]) if row else True

    def set_tab_visibility(self, person_id, tab_key, visible):
        with self._connect() as db:
            db.execute(
                "INSERT INTO person_tab_settings (person_id, tab_key, visible) VALUES (?, ?, ?) "
                "ON CONFLICT(person_id, tab_key) DO UPDATE SET visible = excluded.visible",
                (person_id, tab_key, int(bool(visible))),
            )

    def custom_entries(self, person_id, tab_id):
        with self._connect() as db:
            entries = []
            for row in db.execute("SELECT * FROM custom_entries WHERE person_id = ? AND tab_id = ? ORDER BY id DESC", (person_id, tab_id)):
                entry = dict(row)
                values = self._entry_values(entry)
                entry["values"] = values
                entry.update(values)
                entries.append(entry)
            return entries

    def save_custom_entry(self, person_id, tab_id, values, entry_id=None):
        fields = self.custom_tab_fields(tab_id)
        clean = {field["field_key"]: str(values.get(field["field_key"], "")).strip() for field in fields}
        legacy = tuple(clean.get(key, "") for key in ("concept", "detail", "note"))
        payload = json.dumps(clean, ensure_ascii=False)
        with self._connect() as db:
            if entry_id:
                db.execute(
                    "UPDATE custom_entries SET concept = ?, detail = ?, note = ?, values_json = ? WHERE id = ? AND person_id = ? AND tab_id = ?",
                    (*legacy, payload, entry_id, person_id, tab_id),
                )
            else:
                db.execute(
                    "INSERT INTO custom_entries (person_id, tab_id, concept, detail, note, values_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (person_id, tab_id, *legacy, payload),
                )

    def delete_custom_entry(self, person_id, tab_id, entry_id):
        with self._connect() as db:
            db.execute(
                "DELETE FROM custom_entries WHERE id = ? AND person_id = ? AND tab_id = ?",
                (entry_id, person_id, tab_id),
            )

    @staticmethod
    def _ensure_default_custom_fields(db, tab_id):
        if db.execute("SELECT 1 FROM custom_tab_fields WHERE tab_id = ?", (tab_id,)).fetchone():
            return
        for position, (key, name) in enumerate((("concept", "Concepto"), ("detail", "Detalle"), ("note", "Nota"))):
            db.execute(
                "INSERT OR IGNORE INTO custom_tab_fields (tab_id, field_key, name, position) VALUES (?, ?, ?, ?)",
                (tab_id, key, name, position),
            )

    @staticmethod
    def _entry_values(entry):
        try:
            values = json.loads(entry.get("values_json") or "{}")
            if isinstance(values, dict) and values:
                return values
        except (TypeError, json.JSONDecodeError):
            pass
        return {key: entry.get(key, "") or "" for key in ("concept", "detail", "note")}

    def consult(self, question):
        """Responde consultas sencillas sobre la ficha sin usar ningún servicio externo."""
        text = self._normalise(question)
        if not text:
            return "Escribe una pregunta, por ejemplo: ¿cuál es el número fiscal de Victor?"
        person = self._person_in_question(text)
        if not person:
            sections = self._requested_sections(text)
            if self._is_general_query(text) and sections:
                return self._consult_all(sections)
            return "No pude identificar a la persona. Escribe su nombre tal como aparece en Personas."

        name = " ".join(value for value in (person.get("given_names"), person.get("surname")) if value).strip()
        name = name or person["folder_name"]
        sections = self._requested_sections(text)
        if not sections:
            sections = ("basic",)
        lines = [f"Ficha de {name}"]
        for section in sections:
            lines.extend(self._format_section(section, person))
        return "\n".join(lines)

    @staticmethod
    def _is_general_query(question):
        return any(phrase in question for phrase in (
            "todos los", "todas las", "todos", "todas", "que tengas", "registrados", "registradas",
        ))

    def _consult_all(self, sections):
        table_by_section = {
            "banks": "bank_accounts", "cards": "cards", "emails": "emails", "phones": "phones",
            "services": "services", "insurances": "insurances", "documents": "documents",
            "vehicles": "vehicles", "relations": "family_relations",
        }
        supported = [section for section in sections if section in table_by_section]
        if not supported:
            return "Para una consulta general indica qué quieres ver: emails, teléfonos, seguros, servicios o cuentas." 
        lines = ["Consulta general"]
        for section in supported:
            table = table_by_section[section]
            title, fields = self.RELATED[table]
            lines.append(f"\n{title}:")
            total = 0
            for person in self.people():
                records = self.related(table, person["id"])
                if not records:
                    continue
                name = " ".join(value for value in (person.get("given_names"), person.get("surname")) if value).strip()
                name = name or person["folder_name"]
                for record in records:
                    values = [str(record.get(field, "")).strip() for field in fields if str(record.get(field, "")).strip()]
                    lines.append(f"- {name}: {' · '.join(values)}")
                    total += 1
            if not total:
                lines.append("- No hay registros.")
        return "\n".join(lines)

    def person_in_question(self, question):
        """Devuelve la ficha mencionada en una pregunta, si se puede identificar."""
        return self._person_in_question(self._normalise(question))

    def _person_in_question(self, question):
        matches = []
        for person in self.people():
            names = [person.get("folder_name", ""), person.get("given_names", "")]
            full_name = " ".join(value for value in (person.get("given_names"), person.get("surname")) if value)
            names.append(full_name)
            for name in names:
                normalised = self._normalise(name)
                if normalised and re.search(rf"\b{re.escape(normalised)}\b", question):
                    matches.append((len(normalised), person))
        return max(matches, key=lambda match: match[0])[1] if matches else None

    @staticmethod
    def _requested_sections(question):
        groups = (
            ("tax", ("numero fiscal", "fiscal", "bsn", "impuesto")),
            ("banks", ("cuenta", "cuentas", "banco", "bancaria", "iban")),
            ("cards", ("tarjeta", "tarjetas")),
            ("emails", ("email", "correo", "correo electronico")),
            ("phones", ("telefono", "telefonos", "movil")),
            ("services", ("servicio", "servicios", "suscripcion", "suscripciones", "contrato")),
            ("insurances", ("seguro", "seguros", "poliza")),
            ("documents", ("documento", "documentos", "pasaporte", "identidad")),
            ("vehicles", ("vehiculo", "vehiculos", "coche", "auto")),
            ("relations", ("familia", "familiar", "relacion")),
            ("address", ("direccion", "domicilio", "vive")),
            ("birth", ("nacimiento", "edad", "nacio")),
            ("basic", ("todos los datos", "ficha", "informacion", "datos de")),
        )
        selected = [name for name, words in groups if any(word in question for word in words)]
        return tuple(dict.fromkeys(selected))

    def _format_section(self, section, person):
        if section == "tax":
            return [f"Número fiscal: {person.get('tax_number') or 'No registrado'}"]
        if section == "address":
            values = [person.get(key) for key in ("address", "postcode", "city", "country") if person.get(key)]
            return [f"Dirección: {', '.join(values) if values else 'No registrada'}"]
        if section == "birth":
            return [f"Fecha de nacimiento: {person.get('date_of_birth') or 'No registrada'}"]
        if section == "basic":
            lines = ["Datos básicos:"]
            for label, key in (("Nombre", "given_names"), ("Apellido", "surname"), ("Nacimiento", "date_of_birth"), ("Dirección", "address"), ("Ciudad", "city"), ("País", "country")):
                if person.get(key):
                    lines.append(f"- {label}: {person[key]}")
            return lines or ["No hay datos básicos registrados."]
        table_by_section = {
            "banks": "bank_accounts", "cards": "cards", "emails": "emails", "phones": "phones",
            "services": "services", "insurances": "insurances", "documents": "documents",
            "vehicles": "vehicles", "relations": "family_relations",
        }
        table = table_by_section.get(section)
        if not table:
            return []
        title, fields = self.RELATED[table]
        rows = self.related(table, person["id"])
        if not rows:
            return [f"{title}: no hay registros."]
        lines = [f"{title}:"]
        for row in rows:
            values = [str(row.get(field, "")).strip() for field in fields if str(row.get(field, "")).strip()]
            lines.append(f"- {' · '.join(values)}")
        return lines

    @staticmethod
    def _normalise(value):
        value = unicodedata.normalize("NFD", (value or "").lower())
        value = "".join(char for char in value if not unicodedata.combining(char))
        return " ".join(re.findall(r"[a-z0-9]+", value))

    def get_person(self, person_id):
        with self._connect() as db:
            row = db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
            return dict(row) if row else None

    def save_person(self, values, person_id=None):
        fields = (
            "folder_name", "given_names", "surname", "date_of_birth", "tax_number",
            "reference_notes", "address", "postcode", "city", "country", "note",
        )
        data = [str(values.get(field, "")).strip() for field in fields]
        if not data[0]:
            raise ValueError("Indica la carpeta de documentos de la persona.")
        with self._connect() as db:
            if person_id:
                assignments = ", ".join(f"{field} = ?" for field in fields)
                db.execute(f"UPDATE people SET {assignments} WHERE id = ?", (*data, person_id))
                return person_id
            cursor = db.execute(
                f"INSERT INTO people ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
                data,
            )
            return cursor.lastrowid

    def related(self, table, person_id):
        self._validate_table(table)
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                f"SELECT * FROM {table} WHERE person_id = ? ORDER BY id DESC", (person_id,)
            )]

    def save_related(self, table, person_id, values, record_id=None):
        self._validate_table(table)
        fields = self.RELATED[table][1]
        data = [str(values.get(field, "")).strip() for field in fields]
        with self._connect() as db:
            if record_id:
                assignments = ", ".join(f'"{field}" = ?' for field in fields)
                db.execute(
                    f"UPDATE {table} SET {assignments} WHERE id = ? AND person_id = ?",
                    (*data, record_id, person_id),
                )
            else:
                db.execute(
                    f"INSERT INTO {table} (person_id, {', '.join(f'\"{field}\"' for field in fields)}) "
                    f"VALUES (?, {', '.join('?' for _ in fields)})",
                    (person_id, *data),
                )

    def delete_related(self, table, person_id, record_id):
        self._validate_table(table)
        with self._connect() as db:
            db.execute(f"DELETE FROM {table} WHERE id = ? AND person_id = ?", (record_id, person_id))

    @staticmethod
    def _validate_table(table):
        if table not in FamilyDatabase.RELATED:
            raise ValueError("Tabla de ficha no válida.")

    def import_access(self, access_file, folders_root):
        """Importa datos de Access por una copia de lectura mediante MS Access.

        Las contraseñas se excluyen deliberadamente. El método devuelve el
        número de personas que se han incorporado o actualizado.
        """
        access_file = Path(access_file)
        if not access_file.exists():
            raise FileNotFoundError("No se encontró el archivo de Access seleccionado.")
        data = self._read_access(access_file)
        folders = {folder.name.casefold(): folder.name for folder in Path(folders_root).glob("*") if folder.is_dir()}
        people_by_old_id = {}
        count = 0
        for person in data.get("Personas", []):
            old_id = person.get("IDPersona")
            given = self._text(person.get("Nombres"))
            surname = self._text(person.get("Apellido"))
            full_name = " ".join(value for value in (given, surname) if value).strip()
            folder_name = folders.get(given.casefold()) or folders.get(full_name.casefold()) or given or full_name
            if not folder_name:
                continue
            existing = self._find_person_by_folder(folder_name)
            values = {
                "folder_name": folder_name, "given_names": given or folder_name, "surname": surname,
                "date_of_birth": self._text(person.get("Fecha de Nacimiento")),
                "tax_number": self._text(person.get("Numero Fiscal")),
                "reference_notes": self._text(person.get("Contraseñas Referencia")),
                "address": self._text(person.get("Direccion")), "postcode": self._text(person.get("Postcode")),
                "city": self._text(person.get("Ciudad")), "country": self._text(person.get("Pais")),
                "note": self._text(person.get("Nota")),
            }
            person_id = self.save_person(values, existing["id"] if existing else None)
            people_by_old_id[str(old_id)] = person_id
            count += 1

        for source, target, mapping in self._access_mappings():
            for record in data.get(source, []):
                person_id = people_by_old_id.get(str(record.get("IDPersona")))
                if not person_id:
                    continue
                values = {field: self._text(record.get(access_field)) for field, access_field in mapping.items()}
                self.save_related(target, person_id, values)
        return count

    def _find_person_by_folder(self, folder_name):
        with self._connect() as db:
            row = db.execute("SELECT * FROM people WHERE folder_name = ?", (folder_name,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def _text(value):
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _access_mappings():
        return (
            ("Emails", "emails", {"email": "Email", "type": "TipoEmail", "primary": "Principal", "note": "Nota"}),
            ("Telefonos", "phones", {"phone": "Telefono", "type": "TipoTelefono", "primary": "Principal", "note": "Nota"}),
            ("Servicios", "services", {"service_type": "TipoServicio", "company": "Compania", "client_number": "NumeroCliente", "contract_number": "NumeroContrato", "username": "Usuario", "monthly_price": "PrecioMensual", "billing_day": "FechaCobro", "payment_method": "MetodoPago", "start_date": "FechaInicio", "end_date": "FechaVencimiento", "note": "Nota"}),
            ("Seguros", "insurances", {"insurance_type": "TipoSeguro", "company": "Compañia", "policy_number": "NumeroPoliza", "start_date": "FechaInicio", "end_date": "FechaVencimiento", "monthly_payment": "PagoMensual", "status": "Estado", "note": "Nota"}),
            ("CuentasBancarias", "bank_accounts", {"bank": "Banco", "iban": "IBAN", "account_type": "TipoCuenta", "holder": "Titular", "status": "Estado", "note": "Nota"}),
            ("Tarjetas", "cards", {"bank": "Banco", "card_type": "TipoTarjeta", "last_four": "Ultimos4Digitos", "end_date": "FechaVencimiento", "status": "Estado", "note": "Nota"}),
            ("Documentos", "documents", {"document_type": "TipoDocumento", "document_number": "NumeroDocumento", "issuing_country": "PaisEmision", "issue_date": "FechaEmision", "expiry_date": "FechaVencimiento", "file_path": "RutaArchivo", "status": "Estado", "note": "Nota"}),
            ("Vehiculo", "vehicles", {"brand": "Marca", "model": "Modelo", "registration": "Matricula", "year": "Ano", "colour": "Color", "vin": "VIN", "fuel": "Combustible", "apk_until": "APKHasta", "status": "Estado", "note": "Nota"}),
        )

    @staticmethod
    def _read_access(access_file):
        # Access puede crear archivos de bloqueo al abrir una base. Trabajamos
        # siempre sobre una copia temporal para no tocar el archivo del usuario.
        with tempfile.TemporaryDirectory(prefix="VictorDocumentAI_Access_") as temporary_folder:
            temporary_file = Path(temporary_folder) / Path(access_file).name
            shutil.copy2(access_file, temporary_file)
            return FamilyDatabase._read_access_copy(temporary_file)

    @staticmethod
    def _read_access_copy(access_file):
        tables = [item[0] for item in FamilyDatabase._access_mappings()] + ["Personas"]
        tables_json = json.dumps(tables)
        script = rf'''
$ErrorActionPreference = 'Stop'
$path = $env:VICTOR_DOCUMENT_AI_ACCESS_FILE
$tables = ConvertFrom-Json '{tables_json}'
$access = New-Object -ComObject Access.Application
try {{
  $access.OpenCurrentDatabase($path, $false)
  $db = $access.CurrentDb()
  $result = @{{}}
  foreach ($table in $tables) {{
    $rows = @()
    $recordset = $db.OpenRecordset("SELECT * FROM [$table]")
    while (-not $recordset.EOF) {{
      $row = [ordered]@{{}}
      foreach ($field in $recordset.Fields) {{
        $value = $field.Value
        if ($value -is [datetime]) {{ $value = $value.ToString('yyyy-MM-dd') }}
        $row[$field.Name] = $value
      }}
      $rows += $row
      $recordset.MoveNext()
    }}
    $recordset.Close()
    $result[$table] = $rows
  }}
  [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
  $result | ConvertTo-Json -Depth 6 -Compress
}} finally {{
  if ($access) {{
    try {{ $access.CloseCurrentDatabase() }} catch {{ }}
    try {{ $access.Quit() }} catch {{ }}
  }}
}}
'''
        environment = os.environ.copy()
        environment["VICTOR_DOCUMENT_AI_ACCESS_FILE"] = str(access_file)
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            env=environment,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Access no pudo leer la base de datos.")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError("Access no devolvió datos legibles.") from error
