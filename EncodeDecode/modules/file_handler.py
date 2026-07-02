def read_file(filename):
    """Read and return the full contents of a text file.

    Raises FileNotFoundError with a friendly message if the file is
    missing, so callers can surface a clean error.
    """
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"File tidak ditemukan: {filename}")


def read_lines(filename):
    """Read a file and return a list of non-empty, stripped lines."""
    content = read_file(filename)
    return [line.strip() for line in content.splitlines() if line.strip()]


def write_file(filename, data):
    """Write text data to a file, overwriting any existing content."""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(data)
