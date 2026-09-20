"""İsteğe bağlı destek (bağış) bilgileri: yalnızca USDT (Tether), yalnızca BNB Smart Chain (BSC / BEP-20).

Adres tek bir yerde tutulur; web sayfası ve testler buradan okur, README ise testle bu değerle karşılaştırılır.
`docs/usdt-bsc.svg` bu adresi kodlayan QR'dır; adres değişirse yeniden üretilip testteki özet değeri güncellenmelidir.
"""

from __future__ import annotations

import re

USDT_ADDRESS = "0x315f79cb95f784c18387c3009798d1a617dac8b2"
NETWORK_NAME = "BNB Smart Chain (BSC / BEP-20)"
QR_FILENAME = "usdt-bsc.svg"
ANCHOR = "bagis"

# Yanlış yazılmış bir adres asla yayınlanmasın: para gönderimi geri alınamaz.
if not re.fullmatch(r"0x[0-9a-f]{40}", USDT_ADDRESS):
    raise ValueError("USDT adresi '0x' ve ardından 40 küçük harfli onaltılık karakter olmalı")
