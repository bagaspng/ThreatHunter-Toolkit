import re

def solve_puzzle(question: str):
    q = question.strip()
    
    # Pola 1: Perhitungan huruf vokal atau konsonan
    m = re.search(r"(vokal|konsonan) dalam kata ['\"](\w+)['\"]", q, re.IGNORECASE)
    if m:
        jenis = m.group(1).lower()
        word = m.group(2).lower()
        vokal = set("aiueo")
        if jenis == "vokal":
            return sum(1 for ch in word if ch in vokal)
        else:  # konsonan
            return sum(1 for ch in word if ch.isalpha() and ch not in vokal)
            
    # Pola 2: Operasi matematika dalam kurung siku [a operator b]
    m = re.search(r"\[\s*(-?\d+(?:\.\d+)?)\s*([−\-+×x*÷/])\s*(-?\d+(?:\.\d+)?)\s*\]", q)
    if m:
        a, op, b = m.group(1), m.group(2), m.group(3)
        a, b = float(a), float(b)
        if op in ("−", "-"): result = a - b
        elif op == "+": result = a + b
        elif op in ("×", "x", "*"): result = a * b
        elif op in ("÷", "/"): result = a / b
        else: raise ValueError(f"Operator tidak dikenali: {op}")
        return int(result) if result == int(result) else result
        
    raise ValueError(f"Pola pertanyaan tidak dikenali: {q}")