import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULT_DIR = os.path.join(BASE_DIR, "Result")

def resolve_path(filename):
    if os.path.isabs(filename):
        return filename
    return os.path.join(BASE_DIR, filename)

def resolve_output_path(filename):
    if os.path.isabs(filename):
        return filename
    os.makedirs(RESULT_DIR, exist_ok=True)
    return os.path.join(RESULT_DIR, filename)

def read_file(filename):
    path = resolve_path(filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"File tidak ditemukan: {filename}")

def read_lines(filename):
    content = read_file(filename)
    return [line.strip() for line in content.splitlines() if line.strip()]

def write_file(filename, data):
    path = resolve_output_path(filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)
    return path
