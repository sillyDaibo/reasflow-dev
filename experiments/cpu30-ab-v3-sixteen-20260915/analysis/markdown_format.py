"""Presentation helpers; never modify the frozen evidence or numeric results."""
import re
import unicodedata


def normalize_bold(text):
    """Separate punctuation-ending emphasis from the following CJK/Latin word."""
    def fix(match):
        body = match.group(1)
        after = text[match.end():match.end() + 1]
        if (body and unicodedata.category(body[-1]).startswith('P')
                and after and not after.isspace()
                and not unicodedata.category(after).startswith('P')):
            return match.group(0) + ' '
        return match.group(0)
    return re.sub(r'(?<!\*)\*\*([^*\n]+)\*\*(?!\*)', fix, text)


def literal_prose(text):
    """Protect formula operators and paths, preserving code and deliberate bold."""
    def escape(value):
        value = re.sub(r'([\\`*_\[\]<>|#])', r'\\\1', value)
        value = value.replace('&', '&amp;')
        value = re.sub(r'(?m)^(\s*)([-+])(?=\s)', r'\1\\\2', value)
        return re.sub(r'(?m)^(\s*\d+)([.)])(?=\s)', r'\1\\\2', value)

    text = str(text)
    parts, end = [], 0
    for match in re.finditer(r'`+[^`\n]+`+|\*\*[^*\n]+\*\*', text):
        parts.append(escape(text[end:match.start()]))
        value = match[0]
        if value.startswith('**'):
            body = value[2:-2]
            before = text[match.start() - 1:match.start()] or ' '
            after = text[match.end():match.end() + 1] or ' '
            punct = lambda c: unicodedata.category(c).startswith(('P', 'S'))
            opens = not body[0].isspace() and (not punct(body[0]) or before.isspace() or punct(before))
            closes = not body[-1].isspace() and (not punct(body[-1]) or after.isspace() or punct(after))
            value = '**' + escape(body) + '**' if opens and closes else escape(value)
        parts.append(value)
        end = match.end()
    parts.append(escape(text[end:]))
    return ''.join(parts)


def quote_evidence(text):
    return '\n'.join('> ' + line for line in literal_prose(text).split('\n'))


def code_block(text, language='text'):
    fence = '`' * max(3, max((len(x) + 1 for x in re.findall(r'`+', text)), default=0))
    return f'{fence}{language}\n{text}\n{fence}'


def shift_headings(text, levels):
    return re.sub(r'^(#{1,6}) ', lambda m: '#' * (len(m[1]) + levels) + ' ',
                  text, flags=re.M)
