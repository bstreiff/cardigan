## Cardigan

Cardigan is a Cards Against Humanity style generator for Slack.

## Requirements

- mod_python

I'm using the 'libapache2-mod-python' package from Ubuntu Trusty.

## Installation

- Put it on your webserver somewhere.
- Make sure db_path points to a directory your webserver can read/write.
- Add it as a Slack [custom command](https://my.slack.com/services/new/slash-commands).

## Usage

The following commands are supported. (The following assumes you configured a command of `/cah`.)

- `/cah`
 - Draw a new set of cards.
- `/cah white Text for a new white card`
 - Add a new "white card" (a noun or gerund)
 - The `:white_square:`, `:white_small_square:`, and other "white" emoji symbols can also be used in place of "white".
- `/cah black I think ____ is a great example.`
 - Add a new "black card" (question)
 - The `:black_square:`, `:black_small_square:`, and other "black" emoji symbols can also be used in place of "black".
 - Any sequence of three or more underscores is replaced with `:blank:`.
- `/cah status`
 - Display status about the card pool.
- `/cah search [text]`
 - Search for cards containing the string "text".
- `/cah help`
 - Some help text.

Card pools are scoped to teams.

There is no way at present to edit or remove cards (aside from editing the DB).

## License

Copyright (c) 2016, Brandon Streiff

Permission to use, copy, modify, and/or distribute this software for
any purpose with or without fee is hereby granted, provided that the
above copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL
WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR
BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES
OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,
ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS
SOFTWARE.
