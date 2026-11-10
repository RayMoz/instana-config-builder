"""Kleiner YAML-Leser/-Schreiber als Fallback, wenn PyYAML fehlt."""

import json
import re as _re

# Kleiner YAML-Leser/-Schreiber (Fallback, wenn PyYAML fehlt)
# Unterstützt: Block-Mappings und -Listen, Flow-Listen/-Mappings, Strings in
# '…' und "…", Block-Scalars (| >), Kommentare, YAML-1.1-Typen wie SnakeYAML
# (true/false/yes/no/on/off, Zahlen, null). Nicht unterstützt: Anker,
# Aliase, Tags, mehrzeilige Plain-Scalars.


class MiniYAMLError(ValueError):
    pass


_BOOL_T = {"true", "True", "TRUE", "yes", "Yes", "YES", "on", "On", "ON"}
_BOOL_F = {"false", "False", "FALSE", "no", "No", "NO", "off", "Off", "OFF"}
_NULL = {"", "~", "null", "Null", "NULL"}
_INT = _re.compile(r"^[-+]?(0|[1-9][0-9_]*)$")
_HEX = _re.compile(r"^[-+]?0x[0-9a-fA-F_]+$")
_FLOAT = _re.compile(r"^[-+]?([0-9][0-9_]*)?\.[0-9_]*([eE][-+][0-9]+)?$")


def _resolve(s):
    if s in _NULL:
        return None
    if s in _BOOL_T:
        return True
    if s in _BOOL_F:
        return False
    if _INT.match(s):
        return int(s.replace("_", ""))
    if _HEX.match(s):
        return int(s.replace("_", ""), 16)
    if _FLOAT.match(s) and s not in (".", "+.", "-."):
        return float(s.replace("_", ""))
    if s.lower() in (".inf", "+.inf"):
        return float("inf")
    if s.lower() == "-.inf":
        return float("-inf")
    if s.lower() == ".nan":
        return float("nan")
    return s


def _strip_comment(line):
    q = None
    for i, ch in enumerate(line):
        if q:
            if ch == q:
                if q == "'" and i + 1 < len(line) and line[i + 1] == "'":
                    continue
                if q == '"' and line[i - 1] == "\\":
                    continue
                q = None
        elif ch in "'\"" and (i == 0 or line[i - 1] in " \t[{,:-"):
            q = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line.rstrip()


def _unquote_double(s, ln):
    try:
        return json.loads(s)
    except ValueError:
        body = s[1:-1]
        out = (
            body.replace("\\\\", "\x00")
            .replace('\\"', '"')
            .replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace("\\/", "/")
            .replace("\x00", "\\")
        )
        return out


class _Flow:
    def __init__(self, s, ln):
        self.s, self.i, self.ln = s, 0, ln

    def err(self, msg):
        raise MiniYAMLError("Zeile %d: %s" % (self.ln, msg))

    def ws(self):
        while self.i < len(self.s) and self.s[self.i] in " \t":
            self.i += 1

    def value(self, in_map_key=False):
        self.ws()
        if self.i >= len(self.s):
            self.err("unerwartetes Zeilenende")
        c = self.s[self.i]
        if c == "[":
            self.i += 1
            out = []
            self.ws()
            if self.s[self.i : self.i + 1] == "]":
                self.i += 1
                return out
            while True:
                out.append(self.value())
                self.ws()
                c = self.s[self.i : self.i + 1]
                self.i += 1
                if c == "]":
                    return out
                if c != ",":
                    self.err("',' oder ']' erwartet")
                self.ws()
                if self.s[self.i : self.i + 1] == "]":
                    self.i += 1
                    return out
        if c == "{":
            self.i += 1
            out = {}
            self.ws()
            if self.s[self.i : self.i + 1] == "}":
                self.i += 1
                return out
            while True:
                k = self.value(in_map_key=True)
                self.ws()
                if self.s[self.i : self.i + 1] != ":":
                    self.err("':' erwartet")
                self.i += 1
                v = self.value()
                if k in out:
                    self.err("doppelter Schlüssel '%s'" % k)
                out[k] = v
                self.ws()
                c = self.s[self.i : self.i + 1]
                self.i += 1
                if c == "}":
                    return out
                if c != ",":
                    self.err("',' oder '}' erwartet")
                self.ws()
                if self.s[self.i : self.i + 1] == "}":
                    self.i += 1
                    return out
        if c in "'\"":
            j = self.i + 1
            while True:
                j = self.s.find(c, j)
                if j < 0:
                    self.err("String ohne schließendes Anführungszeichen")
                if c == "'" and self.s[j + 1 : j + 2] == "'":
                    j += 2
                    continue
                if c == '"' and self.s[j - 1] == "\\":
                    j += 1
                    continue
                break
            raw = self.s[self.i : j + 1]
            self.i = j + 1
            return raw[1:-1].replace("''", "'") if c == "'" else _unquote_double(raw, self.ln)
        j = self.i
        stops = ",]}" + (":" if in_map_key else "")
        while j < len(self.s) and self.s[j] not in stops:
            if self.s[j] == ":" and (j + 1 >= len(self.s) or self.s[j + 1] in " ,]}"):
                break
            j += 1
        tok = self.s[self.i : j].strip()
        self.i = j
        return _resolve(tok)


def _inline(s, ln):
    s = s.strip()
    if s[:1] in "&*!":
        raise MiniYAMLError("Zeile %d: Anker, Aliase und Tags werden ohne PyYAML nicht unterstützt" % ln)
    if s[:1] in "[{'\"":
        f = _Flow(s, ln)
        v = f.value()
        f.ws()
        if f.i != len(s):
            raise MiniYAMLError("Zeile %d: unerwarteter Text nach Wert: %r" % (ln, s[f.i :]))
        return v
    return _resolve(s)


def _split_key(text, ln):
    """Liefert (key, rest) oder None, wenn die Zeile kein 'key:' enthält."""
    if text[:1] in "[{":
        return None
    i = 0
    if text[:1] in "'\"":
        q = text[0]
        j = 1
        while True:
            j = text.find(q, j)
            if j < 0:
                return None
            if q == "'" and text[j + 1 : j + 2] == "'":
                j += 2
                continue
            if q == '"' and text[j - 1] == "\\":
                j += 1
                continue
            break
        rest = text[j + 1 :].lstrip()
        if not rest.startswith(":") or (len(rest) > 1 and rest[1] not in " \t"):
            return None
        key = text[1:j].replace("''", "'") if q == "'" else _unquote_double(text[: j + 1], ln)
        return key, rest[1:].strip()
    while i < len(text):
        if text[i] == ":" and (i + 1 == len(text) or text[i + 1] in " \t"):
            return _resolve(text[:i].strip()), text[i + 1 :].strip()
        i += 1
    return None


def mini_load(text, allow_dup=False, warnings=None):
    raw = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    toks = []
    for idx, line in enumerate(raw):
        if line.strip() in ("---", "...") and not line.startswith(" "):
            continue
        body = _strip_comment(line)
        if not body.strip():
            continue
        lead = len(body) - len(body.lstrip(" "))
        if body[lead : lead + 1] == "\t":
            raise MiniYAMLError("Zeile %d: Tabulator in der Einrückung" % (idx + 1))
        toks.append([lead, body.strip(), idx])
    if not toks:
        return None
    p = _Parser(toks, raw)
    p.allow_dup, p.warnings = allow_dup, (warnings if warnings is not None else [])
    val, i = p.block(0, toks[0][0])
    if i < len(toks):
        raise MiniYAMLError("Zeile %d: unerwartete Einrückung" % (toks[i][2] + 1))
    return val


class _Parser:
    def __init__(self, toks, raw):
        self.t, self.raw = toks, raw

    def err(self, i, msg):
        raise MiniYAMLError("Zeile %d: %s" % (self.t[i][2] + 1, msg))

    @staticmethod
    def is_item(text):
        return text == "-" or text.startswith("- ")

    def block(self, i, ind):
        if self.is_item(self.t[i][1]):
            return self.seq(i, ind)
        if _split_key(self.t[i][1], self.t[i][2] + 1) is None:
            if i + 1 < len(self.t) and self.t[i + 1][0] > ind:
                self.err(i + 1, "mehrzeilige Werte werden ohne PyYAML nicht unterstützt")
            return _inline(self.t[i][1], self.t[i][2] + 1), i + 1
        return self.map(i, ind)

    def child(self, i, ind, allow_same_seq):
        """Wert auf den Folgezeilen eines 'key:' bzw. '-'."""
        if i < len(self.t):
            nind, ntext = self.t[i][0], self.t[i][1]
            if nind > ind or (allow_same_seq and nind == ind and self.is_item(ntext)):
                return self.block(i, nind)
        return None, i

    def block_scalar(self, i, ind, indicator):
        start = self.t[i][2] + 1
        lines, j = [], start
        while j < len(self.raw):
            ln = self.raw[j]
            if ln.strip() and (len(ln) - len(ln.lstrip(" "))) <= ind:
                break
            lines.append(ln)
            j += 1
        while lines and not lines[-1].strip():
            lines.pop()
        nonempty = [ln for ln in lines if ln.strip()]
        bi = min(len(ln) - len(ln.lstrip(" ")) for ln in nonempty) if nonempty else 0
        body = [ln[bi:] for ln in lines]
        if indicator.startswith(">"):
            out, para = [], []
            for ln in body:
                if ln.strip():
                    para.append(ln)
                else:
                    out.append(" ".join(para))
                    para = []
            out.append(" ".join(para))
            text = "\n".join(out)
        else:
            text = "\n".join(body)
        eof_no_nl = j >= len(self.raw) and self.raw[-1] != ""
        if "-" not in indicator and text.strip() and not eof_no_nl:
            text += "\n"
        if not text.strip():
            text = ""
        k = i + 1
        while k < len(self.t) and self.t[k][2] < j:
            k += 1
        return text, k

    def map(self, i, ind):
        out = {}
        while i < len(self.t) and self.t[i][0] == ind and not self.is_item(self.t[i][1]):
            sk = _split_key(self.t[i][1], self.t[i][2] + 1)
            if sk is None:
                self.err(i, "'schlüssel: wert' erwartet")
            key, rest = sk
            if key in out:
                if not self.allow_dup:
                    self.err(i, "doppelter Schlüssel '%s'" % key)
                self.warnings.append(
                    "Zeile %d: doppelter Schlüssel '%s' – der spätere Wert gilt" % (self.t[i][2] + 1, key)
                )
                del out[key]
            if rest == "":
                val, i = self.child(i + 1, ind, True)
            elif rest[:1] in "|>" and _re.match(r"^[|>][-+]?[0-9]?$", rest):
                val, i = self.block_scalar(i, ind, rest)
            else:
                val = _inline(rest, self.t[i][2] + 1)
                i += 1
            out[key] = val
        if i < len(self.t) and self.t[i][0] > ind:
            self.err(i, "unerwartete Einrückung")
        return out, i

    def seq(self, i, ind):
        out = []
        while i < len(self.t) and self.t[i][0] == ind and self.is_item(self.t[i][1]):
            text = self.t[i][1]
            rest = text[1:].lstrip()
            col = ind + (len(text) - len(rest))
            if rest == "":
                val, i = self.child(i + 1, ind, False)
            elif self.is_item(rest) or (_split_key(rest, self.t[i][2] + 1) is not None):
                self.t[i] = [col, rest, self.t[i][2]]
                val, i = self.block(i, col)
            elif rest[:1] in "|>" and _re.match(r"^[|>][-+]?[0-9]?$", rest):
                val, i = self.block_scalar(i, ind, rest)
            else:
                val = _inline(rest, self.t[i][2] + 1)
                i += 1
            out.append(val)
        if i < len(self.t) and self.t[i][0] > ind:
            self.err(i, "unerwartete Einrückung")
        return out, i


_SPECIAL_START = set("-?:,[]{}#&*!|>'\"%@`")


def _q(s):
    if "\n" in s or any(ord(c) < 32 for c in s):
        return json.dumps(s, ensure_ascii=False)
    needs = (
        s == ""
        or s != s.strip()
        or s[0] in _SPECIAL_START
        or ": " in s
        or " #" in s
        or s.endswith(":")
        or s in ("=", "<<")
        or not isinstance(_resolve(s), str)
    )
    return "'" + s.replace("'", "''") + "'" if needs else s


def _scalar_out(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    return _q(str(v))


def mini_dump(v, ind=0):
    pad = " " * ind
    lines = []
    if isinstance(v, dict):
        if not v:
            return pad + "{}"
        for k, x in v.items():
            kk = _scalar_out(k) if not isinstance(k, str) else _q(k)
            if isinstance(x, dict) and x:
                lines.append(pad + kk + ":")
                lines.append(mini_dump(x, ind + 2))
            elif isinstance(x, list) and x:
                lines.append(pad + kk + ":")
                lines.append(mini_dump(x, ind))
            elif isinstance(x, (dict, list)):
                lines.append(pad + kk + ": " + ("{}" if isinstance(x, dict) else "[]"))
            else:
                lines.append(pad + kk + ": " + _scalar_out(x))
        return "\n".join(lines)
    if isinstance(v, list):
        if not v:
            return pad + "[]"
        for x in v:
            if isinstance(x, (dict, list)) and x:
                sub = mini_dump(x, ind + 2)
                lines.append(pad + "- " + sub[ind + 2 :])
            elif isinstance(x, (dict, list)):
                lines.append(pad + "- " + ("{}" if isinstance(x, dict) else "[]"))
            else:
                lines.append(pad + "- " + _scalar_out(x))
        return "\n".join(lines)
    return pad + _scalar_out(v)
