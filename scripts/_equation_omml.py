from __future__ import annotations

from dataclasses import dataclass

from scripts._docx_xml import create_word_element, word_qn


GREEK_LETTERS = {
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "epsilon": "ε",
    "theta": "θ",
    "lambda": "λ",
    "mu": "μ",
    "pi": "π",
    "sigma": "σ",
    "phi": "φ",
    "omega": "ω",
}


class UnsupportedEquationSyntax(ValueError):
    pass


@dataclass
class EquationParser:
    latex: str
    position: int = 0

    def parse(self) -> list[dict[str, object]]:
        nodes = self.parse_sequence()
        self.skip_whitespace()
        if self.position != len(self.latex):
            raise UnsupportedEquationSyntax(self.latex)
        return nodes

    def skip_whitespace(self) -> None:
        while self.position < len(self.latex) and self.latex[self.position].isspace():
            self.position += 1

    def parse_sequence(self, stop_char: str | None = None) -> list[dict[str, object]]:
        nodes: list[dict[str, object]] = []
        while self.position < len(self.latex):
            self.skip_whitespace()
            if self.position >= len(self.latex):
                break
            current = self.latex[self.position]
            if stop_char is not None and current == stop_char:
                break
            if current in "^_":
                raise UnsupportedEquationSyntax(self.latex)
            node = self.parse_atom()
            while True:
                self.skip_whitespace()
                if self.position >= len(self.latex) or self.latex[self.position] not in "^_":
                    break
                operator = self.latex[self.position]
                self.position += 1
                argument = self.parse_script_argument()
                if operator == "^":
                    if node.get("kind") == "sub":
                        node = {
                            "kind": "subsup",
                            "base": node["base"],
                            "sub": node["sub"],
                            "sup": argument,
                        }
                    elif node.get("kind") == "subsup":
                        node["sup"] = argument
                    else:
                        node = {"kind": "sup", "base": node, "sup": argument}
                else:
                    if node.get("kind") == "sup":
                        node = {
                            "kind": "subsup",
                            "base": node["base"],
                            "sub": argument,
                            "sup": node["sup"],
                        }
                    elif node.get("kind") == "subsup":
                        node["sub"] = argument
                    else:
                        node = {"kind": "sub", "base": node, "sub": argument}
            nodes.append(node)
        return nodes

    def parse_atom(self) -> dict[str, object]:
        current = self.latex[self.position]
        if current == "{":
            return {"kind": "group", "children": self.parse_group()}
        if current == "\\":
            return self.parse_command()
        self.position += 1
        return {"kind": "text", "text": current}

    def parse_group(self) -> list[dict[str, object]]:
        if self.latex[self.position] != "{":
            raise UnsupportedEquationSyntax(self.latex)
        self.position += 1
        children = self.parse_sequence("}")
        if self.position >= len(self.latex) or self.latex[self.position] != "}":
            raise UnsupportedEquationSyntax(self.latex)
        self.position += 1
        return children

    def parse_script_argument(self) -> dict[str, object]:
        self.skip_whitespace()
        if self.position >= len(self.latex):
            raise UnsupportedEquationSyntax(self.latex)
        if self.latex[self.position] == "{":
            return {"kind": "group", "children": self.parse_group()}
        return self.parse_atom()

    def parse_command(self) -> dict[str, object]:
        if self.latex.startswith("\\begin", self.position):
            raise UnsupportedEquationSyntax(self.latex)
        self.position += 1
        start = self.position
        while self.position < len(self.latex) and self.latex[self.position].isalpha():
            self.position += 1
        name = self.latex[start : self.position]
        if not name:
            raise UnsupportedEquationSyntax(self.latex)
        if name == "frac":
            return {
                "kind": "frac",
                "num": {"kind": "group", "children": self.parse_group()},
                "den": {"kind": "group", "children": self.parse_group()},
            }
        if name == "sqrt":
            return {
                "kind": "sqrt",
                "value": {"kind": "group", "children": self.parse_group()},
            }
        if name in GREEK_LETTERS:
            return {"kind": "text", "text": GREEK_LETTERS[name]}
        raise UnsupportedEquationSyntax(self.latex)


def _node_children(node: dict[str, object]) -> list[dict[str, object]]:
    if node.get("kind") == "group":
        return list(node.get("children", []))
    return [node]


def _append_text(container, text: str) -> None:
    run = create_word_element("m:r")
    text_element = create_word_element("m:t")
    text_element.text = text
    run.append(text_element)
    container.append(run)


def _append_nodes(container, nodes: list[dict[str, object]]) -> None:
    for node in nodes:
        kind = node.get("kind")
        if kind == "text":
            _append_text(container, str(node.get("text", "")))
            continue
        if kind == "group":
            _append_nodes(container, list(node.get("children", [])))
            continue
        if kind == "frac":
            fraction = create_word_element("m:f")
            numerator = create_word_element("m:num")
            denominator = create_word_element("m:den")
            _append_nodes(numerator, _node_children(node["num"]))
            _append_nodes(denominator, _node_children(node["den"]))
            fraction.append(numerator)
            fraction.append(denominator)
            container.append(fraction)
            continue
        if kind == "sqrt":
            radical = create_word_element("m:rad")
            degree_hidden = create_word_element("m:degHide")
            degree_hidden.set(word_qn("m:val"), "1")
            element = create_word_element("m:e")
            _append_nodes(element, _node_children(node["value"]))
            radical.append(degree_hidden)
            radical.append(element)
            container.append(radical)
            continue
        if kind == "sup":
            superscript = create_word_element("m:sSup")
            base = create_word_element("m:e")
            exponent = create_word_element("m:sup")
            _append_nodes(base, _node_children(node["base"]))
            _append_nodes(exponent, _node_children(node["sup"]))
            superscript.append(base)
            superscript.append(exponent)
            container.append(superscript)
            continue
        if kind == "sub":
            subscript = create_word_element("m:sSub")
            base = create_word_element("m:e")
            index = create_word_element("m:sub")
            _append_nodes(base, _node_children(node["base"]))
            _append_nodes(index, _node_children(node["sub"]))
            subscript.append(base)
            subscript.append(index)
            container.append(subscript)
            continue
        if kind == "subsup":
            subscript_superscript = create_word_element("m:sSubSup")
            base = create_word_element("m:e")
            index = create_word_element("m:sub")
            exponent = create_word_element("m:sup")
            _append_nodes(base, _node_children(node["base"]))
            _append_nodes(index, _node_children(node["sub"]))
            _append_nodes(exponent, _node_children(node["sup"]))
            subscript_superscript.append(base)
            subscript_superscript.append(index)
            subscript_superscript.append(exponent)
            container.append(subscript_superscript)
            continue
        raise UnsupportedEquationSyntax(str(node))


def latex_to_omml(latex: str):
    parser = EquationParser(latex.strip())
    nodes = parser.parse()
    equation = create_word_element("m:oMath")
    _append_nodes(equation, nodes)
    return equation
