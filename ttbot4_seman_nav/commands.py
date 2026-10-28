"""Accent-insensitive Vietnamese route parser with strict unknown-region handling."""
import re
import unicodedata


def normalize(text):
    text = unicodedata.normalize('NFD', str(text).lower().replace('đ', 'd'))
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', text)).strip()


class CommandParser:
    def __init__(self, regions):
        self.aliases = {}
        for r in regions:
            aliases = [r['id'], r['name'], *r.get('aliases', [])]
            # Bare IDs and "khu vuc A" both resolve, without substring matches.
            aliases += ['khu vuc ' + r['id'], 'phong ' + r['id']]
            for alias in aliases:
                key = normalize(alias)
                if not key or (key in self.aliases and self.aliases[key] != r['id']):
                    raise ValueError(f'Ambiguous/empty region alias: {alias}')
                self.aliases[key] = r['id']

    def parse(self, text):
        text = normalize(text)
        if text in ('dung', 'dung lai', 'huy', 'huy dieu huong'):
            return None
        # Grammar: [di/chuyen...] (tu X den Y | den X | tu X qua Y roi den Z).
        text = re.sub(r'^(?:hay |robot |vui long )+', '', text)
        text = re.sub(r'^(?:di chuyen|dieu huong|di)(?: robot)?\s+', '', text)
        if not text.startswith(('tu ', 'den ', 'toi ')):
            raise ValueError('Câu lệnh cần có “đến …” hoặc “từ … đến …”.')
        text = re.sub(r'^(tu|den|toi)\s+', '', text)
        parts = re.split(r'\s+(?:roi den|roi toi|den|toi|qua)\s+', text)
        route = []
        for part in parts:
            if part not in self.aliases:
                raise ValueError(f'Khu vực không tồn tại: {part}')
            region = self.aliases[part]
            if not route or route[-1] != region:
                route.append(region)
        return route
