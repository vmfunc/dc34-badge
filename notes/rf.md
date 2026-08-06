# rf / wireless

badge-to-badge is usually where the interesting challenges are, because it is the one
surface you cannot solve by staring at your own badge alone.

## what it transmits

| band | modulation | when | notes |
| --- | --- | --- | --- |
| | | | |

order of work:

1. **passive first.** wide sweep, find the carrier, do not transmit anything on the
   con floor until you know what you would be stepping on.
2. capture to `captures/rf/` (gitignored, hash it in the sibling MANIFEST).
3. demod in urh / inspectrum, get to bits before you get to bytes.
4. only then replay, and only then fuzz.

## protocol

frame layout, preamble, sync word, crc polynomial, addressing. sketch the frame here
as soon as you have two captures that differ in exactly one field.

## legal / etiquette

transmitting at defcon is not a free-for-all. passive receive is always fine. active
transmit: know the band, keep the power down, and do not jam. the badge CTF is not
worth an FCC conversation.
