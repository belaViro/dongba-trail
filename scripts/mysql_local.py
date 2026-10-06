"""Start an isolated loopback MySQL instance using the installed MySQL binaries."""

import argparse
import ctypes
import json
import os
import secrets
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

import pymysql
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "mysql"
STATE = RUNTIME / "local-secrets.json"
DATABASES = ("dongba", "dongba_test", "dongba_ui", "dongba_rag", "dongba_rag_test")


def mysql_path(path: Path) -> str:
    if os.name != "nt":
        return path.as_posix()
    buffer = ctypes.create_unicode_buffer(32768)
    length = ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, len(buffer))
    return buffer.value.replace("\\", "/") if length else path.as_posix()


def connect(state, password):
    return pymysql.connect(
        host="127.0.0.1",
        port=state["port"],
        user="root",
        password=password,
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=2,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=3307)
    args = parser.parse_args()
    binary = shutil.which("mysqld")
    if not binary:
        raise SystemExit("Install MySQL 8.0+ and add mysqld to PATH first")
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if STATE.exists():
        state = json.loads(STATE.read_text(encoding="utf-8"))
    else:
        state = {
            "port": args.port,
            "password": secrets.token_urlsafe(30),
            "root_password": secrets.token_urlsafe(40),
            "bootstrapped": False,
        }
        STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    datadir = RUNTIME / "data"
    datadir.mkdir(exist_ok=True)
    config = RUNTIME / "my.ini"
    config.write_text(
        "[mysqld]\n"
        f'basedir="{Path(binary).resolve().parents[1].as_posix()}"\n'
        f'datadir="{mysql_path(datadir)}"\n'
        f"port={state['port']}\n"
        "bind-address=127.0.0.1\nmysqlx=0\nskip-log-bin\n"
        "character-set-server=utf8mb4\ncollation-server=utf8mb4_unicode_ci\n"
        "local-infile=0\nsecure-file-priv=NULL\ninnodb-buffer-pool-size=128M\n"
        f'log-error="{mysql_path(RUNTIME)}/mysql.log"\n',
        encoding="utf-8",
    )
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    command = [binary, f"--defaults-file={mysql_path(config)}"]
    if not (datadir / "mysql").exists():
        datadir.mkdir(exist_ok=True)
        print("Initializing project-local MySQL data directory", flush=True)
        subprocess.run(
            [*command, "--initialize-insecure"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )

    with socket.socket() as probe:
        listening = probe.connect_ex(("127.0.0.1", state["port"])) == 0
    if not listening:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        (RUNTIME / "process-id").write_text(str(process.pid), encoding="ascii")

    connection = None
    for attempt in range(40):
        try:
            try:
                connection = connect(state, state["root_password"])
            except pymysql.err.OperationalError:
                if state["bootstrapped"]:
                    raise
                connection = connect(state, "")
            break
        except pymysql.err.OperationalError:
            if attempt == 39:
                raise SystemExit(
                    "MySQL did not become ready; inspect runtime/mysql/mysql.log"
                ) from None
            time.sleep(0.5)
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT @@datadir, VERSION()")
            actual_datadir, version = cursor.fetchone()
            if Path(actual_datadir).resolve() != datadir.resolve():
                raise SystemExit("Port belongs to another MySQL instance; no changes performed")
            if not state["bootstrapped"]:
                cursor.execute(
                    "ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (state["root_password"],)
                )
                state["bootstrapped"] = True
                STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
            for database in DATABASES:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            cursor.execute(
                "CREATE USER IF NOT EXISTS 'dongba'@'127.0.0.1' IDENTIFIED BY %s",
                (state["password"],),
            )
            for database in DATABASES:
                cursor.execute(
                    "GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,ALTER,DROP,INDEX,REFERENCES "
                    f"ON `{database}`.* TO 'dongba'@'127.0.0.1'"
                )

    base = f"mysql+pymysql://dongba:{quote(state['password'], safe='')}@127.0.0.1:{state['port']}"
    environment_path = ROOT / ".env"
    environment = dotenv_values(environment_path)
    for key, value in {
        "DONGBA_DATABASE_URL": f"{base}/dongba?charset=utf8mb4",
        "DONGBA_TEST_DATABASE_URL": f"{base}/dongba_test?charset=utf8mb4",
        "DONGBA_UI_DATABASE_URL": f"{base}/dongba_ui?charset=utf8mb4",
        "DONGBA_RAG_DATABASE_URL": f"{base}/dongba_rag?charset=utf8mb4",
        "DONGBA_TEST_RAG_DATABASE_URL": f"{base}/dongba_rag_test?charset=utf8mb4",
    }.items():
        if not environment.get(key):
            set_key(environment_path, key, value)
    print(f"MySQL {version} ready on 127.0.0.1:{state['port']}; databases: {', '.join(DATABASES)}")
    print("Connection secrets are stored locally in ignored files; none are printed")


if __name__ == "__main__":
    main()
