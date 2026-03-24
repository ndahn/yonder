from typing import Iterable, Generator, Callable, TYPE_CHECKING
from abc import ABC, abstractmethod
import re
from lark import Lark, Transformer, Token
from fnmatch import fnmatch
from rapidfuzz import fuzz

if TYPE_CHECKING:
    from yonder import Node


lucene_grammar = r"""
    ?start: or_expr

    ?or_expr: and_expr (KW_OR and_expr)*        -> or_
    ?and_expr: not_expr (KW_AND not_expr)* 
             | not_expr not_expr+               -> and_
    ?not_expr: KW_NOT not_expr                  -> not_
             | atom

    ?atom: field
         | bare_value
         | "(" or_expr ")"

    field: PATH_OR_STR "=" VALUE_TOKEN          -> field
    bare_value: VALUE_TOKEN                     -> value

    ESCAPED_STRING: SINGLE_QUOTED_STRING | DOUBLE_QUOTED_STRING
    SINGLE_QUOTED_STRING: "'" ( /[^'\\]/ | /\\./ )* "'"
    DOUBLE_QUOTED_STRING: "\"" ( /[^"\\]/ | /\\./ )* "\""
    PATH_OR_STR: PATH | ESCAPED_STRING

    KW_AND: /(?i:AND)\b/
    KW_OR:  /(?i:OR)\b/
    KW_NOT: /(?i:NOT)\b/

    VALUE_TOKEN: RANGE | FUZZY | ESCAPED_STRING | NONKEYWORD
    PATH      : /[A-Za-z_][A-Za-z0-9_.:*\/]*/
    RANGE     : /\[[^\[\]]+\.\.[^\[\]]+\]/
    FUZZY     : /~[^\s()]+/
    NONKEYWORD: /(?![Aa][Nn][Dd]\b|[Oo][Rr]\b|[Nn][Oo][Tt]\b)[^\s()]+/

    %import common.WS
    %ignore WS
"""


lucene_url = "https://lucene.apache.org/core/2_9_4/queryparsersyntax.html"


query_help_text = """\
Supports Lucene-style search queries (<field>=<value>). 

- You may use the * wildcard for values
- You may use the * and ** wildcards for field paths
- Use [X..Y] to specify a value range
- Precede your value with tilde ~ to do a fuzzy search
- Terms may be combined using grouping, OR, NOT. 
- Terms separated by a space are assumed to be AND.

You may run queries over the following fields:
- id, type, name
- parent
- any attribute path separated by forward slashes /

Examples:
- id=*588 OR type=RandomSequenceContainer
- node_base_params/rtcp:0/id=12345
- NOT node_base_params/parent_id=[100000..200000]
- name=~Play_s*
"""


class _Condition(ABC):
    @abstractmethod
    def evaluate(self, obj: "Node") -> bool: ...


class _FieldCondition(_Condition):
    def __init__(self, field_path: str, value: str):
        self.field_path = field_path.strip("\"'")
        self.value = value.strip("\"'")

    def _get_field_values(self, node: "Node") -> list[str]:
        if self.field_path == "id":
            return [node.id]

        if self.field_path == "type":
            return [node.type]

        return [str(v) for _, v in node.resolve_path(self.field_path, [])]

    def evaluate(self, obj: "Node") -> bool:
        actual_values = self._get_field_values(obj)
        return any(_match_value(val, self.value) for val in actual_values)

    def __repr__(self):
        return f"field({self.field_path}={self.value})"


class _ValueCondition(_Condition):
    def __init__(self, value: str):
        self.value = value.strip("\"'")

    def _candidates(self, node: "Node") -> Generator[str, None, None]:
        yield node.id
        yield node.type
        yield node.lookup_name()

    def evaluate(self, obj: "Node") -> bool:
        return any(_match_value(val, self.value) for val in self._candidates(obj))

    def __repr__(self):
        return f"value({self.value})"


class _OrCondition(_Condition):
    def __init__(self, conditions: list[_Condition]):
        self.conditions = conditions

    def evaluate(self, obj: "Node") -> bool:
        return any(c.evaluate(obj) for c in self.conditions)

    def __repr__(self):
        return f"OR({', '.join(map(str, self.conditions))})"


class _AndCondition(_Condition):
    def __init__(self, conditions: list[_Condition]):
        self.conditions = conditions

    def evaluate(self, node: "Node") -> bool:
        return all(c.evaluate(node) for c in self.conditions)

    def __repr__(self):
        return f"AND({', '.join(map(str, self.conditions))})"


class _NotCondition(_Condition):
    def __init__(self, condition: _Condition):
        self.condition = condition

    def evaluate(self, obj: "Node") -> bool:
        # Special-case: NOT on a field requires the field to exist
        if isinstance(self.condition, _FieldCondition):
            vals = self.condition._get_field_values(obj)
            if not vals:
                # No match if the field isn't present
                return False

            return not any(_match_value(v, self.condition.value) for v in vals)

        return not self.condition.evaluate(obj)

    def __repr__(self):
        return f"NOT({self.condition})"


class _QueryTransformer(Transformer):
    def _conds(self, args):
        # drop KW_AND / KW_OR / KW_NOT tokens
        return [a for a in args if not isinstance(a, Token)]

    def field(self, args):
        path, value = str(args[0]), str(args[1]).strip("\"'")
        return _FieldCondition(path, value)

    def value(self, args):
        value = str(args[0]).strip("\"'")
        return _ValueCondition(value)

    def or_(self, args):
        return _OrCondition(self._conds(args))

    def and_(self, args):
        return _AndCondition(self._conds(args))

    def not_(self, args):
        return _NotCondition(self._conds(args)[0])


def _parse_query(query_string: str) -> _Condition:
    parser = Lark(lucene_grammar, parser="earley")
    tree = parser.parse(query_string)
    return _QueryTransformer().transform(tree)


def _match_value(actual_value: str, search_value: str) -> bool:
    if actual_value is None:
        return False

    if search_value == "*":
        return True

    actual_value = str(actual_value)

    if search_value.startswith("~"):
        fuzzy_term = search_value[1:]
        return fuzz.partial_ratio(actual_value.lower(), fuzzy_term.lower()) > 80

    elif "*" in search_value:
        return fnmatch(actual_value.lower(), search_value.lower())

    elif (
        search_value.startswith("[")
        and search_value.endswith("]")
        and ".." in search_value
    ):
        try:
            m = re.match(r"\[(\S+)\.\.(\S+)\]", search_value)
            if m:
                start, end = m.groups()
                val = float(actual_value)
                return float(start) <= val <= float(end)
        except ValueError:
            return False

        return False

    else:
        return actual_value.lower() == search_value.lower()


def query_nodes(
    candidates: Iterable["Node"],
    query: str,
    object_filter: Callable[["Node"], bool] = None,
) -> Generator["Node", None, None]:
    if not query:
        yield from filter(object_filter, candidates)
        return

    condition = None

    try:
        condition = _parse_query(query)
        for obj in candidates:
            if object_filter and not object_filter(obj):
                continue

            if condition.evaluate(obj):
                yield obj

    except Exception as e:
        s = str(condition) if condition else query
        raise ValueError(f"Query {s} failed") from e
