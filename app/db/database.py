from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "cause_list.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                file_hash TEXT NOT NULL UNIQUE,
                uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                page_count INTEGER,
                court_establishment TEXT,
                court_number TEXT,
                judge_name TEXT,
                case_category TEXT,
                cause_list_date TEXT
            );

            CREATE TABLE IF NOT EXISTS cause_list_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,

                source_file TEXT,
                source_page INTEGER,

                listing_date TEXT,
                court_establishment TEXT,
                court_number TEXT,
                judge_name TEXT,
                case_category TEXT,

                stage TEXT,
                serial_number INTEGER,

                case_reference TEXT,
                case_type TEXT,
                case_number TEXT,
                case_year TEXT,

                party_name TEXT,
                advocate TEXT,

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(document_id) REFERENCES documents(id),

                UNIQUE (
                    listing_date,
                    court_number,
                    stage,
                    serial_number,
                    case_reference,
                    party_name
                )
            );

            CREATE TABLE IF NOT EXISTS case_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,

                source_file TEXT,
                source_page INTEGER,

                case_type TEXT,
                filing_number TEXT,
                filing_date TEXT,
                registration_number TEXT,
                registration_date TEXT,
                cnr_number TEXT,

                first_hearing_date TEXT,
                next_hearing_date TEXT,
                case_status TEXT,
                stage_of_case TEXT,
                court_number_and_judge TEXT,

                detail_text TEXT,

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(document_id) REFERENCES documents(id),

                UNIQUE (
                    document_id,
                    registration_number,
                    cnr_number
                )
            );

            CREATE TABLE IF NOT EXISTS case_parties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_detail_id INTEGER NOT NULL,
                party_type TEXT,
                party_number INTEGER,
                party_name TEXT,
                advocate_name TEXT,
                FOREIGN KEY(case_detail_id) REFERENCES case_details(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS case_acts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_detail_id INTEGER NOT NULL,
                act_name TEXT,
                section_text TEXT,
                FOREIGN KEY(case_detail_id) REFERENCES case_details(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS case_fir_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_detail_id INTEGER NOT NULL,
                police_station TEXT,
                fir_number TEXT,
                fir_year TEXT,
                FOREIGN KEY(case_detail_id) REFERENCES case_details(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS case_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_detail_id INTEGER NOT NULL,
                registration_number TEXT,
                judge TEXT,
                business_on_date TEXT,
                hearing_date TEXT,
                purpose_of_hearing TEXT,
                FOREIGN KEY(case_detail_id) REFERENCES case_details(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS case_process_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_detail_id INTEGER NOT NULL,
                process_id TEXT,
                process_date TEXT,
                process_title TEXT,
                issued_process TEXT,
                FOREIGN KEY(case_detail_id) REFERENCES case_details(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS case_transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_detail_id INTEGER NOT NULL,
                registration_number TEXT,
                transfer_date TEXT,
                from_court TEXT,
                to_court TEXT,
                FOREIGN KEY(case_detail_id) REFERENCES case_details(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS case_subordinate_courts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_detail_id INTEGER NOT NULL,
                court_number_and_name TEXT,
                case_number_and_year TEXT,
                case_decision_date TEXT,
                FOREIGN KEY(case_detail_id) REFERENCES case_details(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS case_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_detail_id INTEGER NOT NULL,
                order_number TEXT,
                order_date TEXT,
                order_details TEXT,
                FOREIGN KEY(case_detail_id) REFERENCES case_details(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_case_details_registration_number
            ON case_details(registration_number);

            CREATE INDEX IF NOT EXISTS idx_case_details_cnr_number
            ON case_details(cnr_number);

            CREATE INDEX IF NOT EXISTS idx_case_details_stage
            ON case_details(stage_of_case);

            CREATE INDEX IF NOT EXISTS idx_case_history_case_detail
            ON case_history(case_detail_id);

            CREATE INDEX IF NOT EXISTS idx_case_parties_case_detail
            ON case_parties(case_detail_id);

            CREATE INDEX IF NOT EXISTS idx_documents_file_hash
            ON documents(file_hash);

            CREATE INDEX IF NOT EXISTS idx_cause_listing_date
            ON cause_list_items(listing_date);

            CREATE INDEX IF NOT EXISTS idx_cause_court_number
            ON cause_list_items(court_number);

            CREATE INDEX IF NOT EXISTS idx_cause_stage
            ON cause_list_items(stage);

            CREATE INDEX IF NOT EXISTS idx_cause_case_reference
            ON cause_list_items(case_reference);

            CREATE INDEX IF NOT EXISTS idx_cause_advocate
            ON cause_list_items(advocate);

            CREATE INDEX IF NOT EXISTS idx_cause_party_name
            ON cause_list_items(party_name);
            """
        )