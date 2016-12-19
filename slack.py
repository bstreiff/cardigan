#!/usr/bin/python
#
# Cardigan - A Cards-Against-Humanity-style generator for Slack
#
#    Part of the Salt Force Five project.
#
# Copyright (c) 2016, Brandon Streiff 
#
# Permission to use, copy, modify, and/or distribute this software for
# any purpose with or without fee is hereby granted, provided that the
# above copyright notice and this permission notice appear in all
# copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL
# WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE
# AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL
# DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR
# PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
# TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.
#

from mod_python import apache
from mod_python import util
import json
import random
import re
import sqlite3

db_path = "/var/lib/www/cah"

blank_pattern = ":blank:"
black_emoji = (":black_square:", ":black_small_square:", ":black_medium_small_square:",
               ":black_medium_square:", ":black_large_square:", ":black_circle:", "black")
white_emoji = (":white_square:", ":white_small_square:", ":white_medium_small_square:",
               ":white_medium_square:", ":white_large_square:", ":white_circle:", "white")

class SlackError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

# Return the number of blanks in a string.
def get_blank_count(text):
    appears = text.count(blank_pattern);
    if (appears == 0):
        return 1
    else:
        return appears

def conjoin(ary):
    if (len(ary) == 0):
        return ""
    elif (len(ary) == 1):
        return str(ary[0])
    elif (len(ary) == 2):
        return str(ary[0]) + " and " + str(ary[1])
    else:
        return ary[0:-1].join(", ") + ", and " + str(ary[-1])

def remove_first_word(text):
    first, _, rest = text.partition(" ")
    return rest or first

def round_as_text(black_card, white_cards):
    text = black_card.text
    top_card = 0;

    while (text.count(blank_pattern) > 0):
        answer = "*" + white_cards[top_card].text + "*"
        top_card += 1
        text = text.replace(blank_pattern, answer, 1);

    # If cards left over, then the end is implied to be a blank.
    if (top_card < len(white_cards)):
        text = text + " " + conjoin([ c.text for c in white_cards[top_card:] ]) + "."

    return text

def round_as_dict(black_card, white_cards):
    return {
        'black_card': black_card.as_dict(),
        'white_cards': [ w.as_dict() for w in white_cards ]
    }

def normalize_blanks(text):
    text = re.sub(r'_{3,}\s+([,.!?])', ':blank:\g<1>', text)
    text = re.sub(r'_{3,}', ':blank:', text);
    return text

class User:
    def __init__(self, id, name):
        self.id = id
        self.name = name

class BlackCard:
    def __init__(self, text, draw=None, pick=None, author=None, card_id=None):
        self.text = text
        self.author = author
        self.card_id = card_id

        if pick is None:
            self.pick = get_blank_count(text)
        else:
            self.pick = pick

        if draw is None:
            if self.pick >= 3:
                self.draw = self.pick - 1
            else:
                self.draw = 0
        else:
            self.draw = draw;

    def as_dict(self):
        return { 'text': self.text,
                 'draw': self.draw,
                 'pick': self.pick,
                 'card_id': self.card_id }                 

class WhiteCard:
    def __init__(self, text, author=None, card_id=None):
        self.text = text
        self.author = author
        self.card_id = card_id

    def as_dict(self):
        return { 'text': self.text,
                 'card_id': self.card_id }

def is_valid_id(text):
    pattern = re.compile("^([A-Za-z0-9])+$")
    return pattern.match(text)

class DeckStatus:
    def __init__(self, black_card_count, white_card_count):
        self.black_card_count = black_card_count
        self.white_card_count = white_card_count

class Deck:
    def __init__(self, deck_name):
        if not is_valid_id(deck_name):
            raise ValueError("bad deck name")

        self.connection = sqlite3.connect(db_path + "/" + deck_name + "-cards.db")

        self.connection.execute("create table if not exists black_cards (" +
                         "id          integer primary key, " +
                         "text        varchar, " +
                         "draw        integer, " +
                         "pick        integer, " +
                         "user_id     varchar, " +
                         "user_name   varchar  " +
                     ")")
        self.connection.execute("create table if not exists white_cards (" +
                         "id          integer primary key, " +
                         "text        varchar, " +
                         "user_id     varchar, " +
                         "user_name   varchar  " +
                     ")")

    def draw_black(self):
        cursor = self.connection.cursor()
        # "ORDER BY RANDOM() LIMIT 1" isn't good for performance,
        # but my thought is that the sample size will be low enough
        # that I'm choosing not to worry about this now.
        cursor.execute("select text, draw, pick, user_id, user_name, id from black_cards order by RANDOM() limit 1")
        row = cursor.fetchone();
        if (row is None):
            raise SlackError("Not enough black cards!")
        (text, draw, pick, user_id, user_name, card_id) = row;

        return BlackCard(text=text, draw=draw, pick=pick,
                         author=User(id=user_id, name=user_name),
                         card_id=card_id)

    def draw_whites(self, count=1):
        cursor = self.connection.cursor()
        cursor.execute("select text, user_id, user_name, id from white_cards order by RANDOM() limit ?", str(count))
        results = []
        for i in range(0, count):
            row = cursor.fetchone();
            if (row is None):
                raise SlackError("Not enough white cards!")
            (text, user_id, user_name, card_id) = row
            results.append(WhiteCard(text=text,
                                     author=User(id=user_id, name=user_name),
                                     card_id=card_id))
        return results

    def save_black(self, black_card):
        cursor = self.connection.cursor()
        cursor.execute("insert into black_cards ("
                           "text, draw, pick, user_id, user_name) " +
                       "values (?,?,?,?,?)", (
                           black_card.text,
                           black_card.draw,
                           black_card.pick,
                           black_card.author.id,
                           black_card.author.name))
        self.connection.commit()
        return

    def save_white(self, white_card):
        cursor = self.connection.cursor()
        cursor.execute("insert into white_cards ("
                           "text, user_id, user_name) " +
                       "values (?,?,?)", (
                           white_card.text,
                           white_card.author.id,
                           white_card.author.name))
        self.connection.commit()
        return

    def get_status(self):
        cursor = self.connection.cursor()
        cursor.execute("select count(*) from white_cards");
        white_card_count = cursor.fetchone()[0]
        cursor.execute("select count(*) from black_cards");
        black_card_count = cursor.fetchone()[0]
        return DeckStatus(white_card_count=white_card_count,
                          black_card_count=black_card_count)

def handle_status(deck):
    status = deck.get_status()

    text = "Cards: :white_square: {0}, :black_square: {1}".format(
        status.white_card_count, status.black_card_count);

    return {
        'response_type': 'in_channel',
        'text': text
    }

def handle_new_card(color, deck, author, text):
    if color == 'white':
        new_card = WhiteCard(text=text, author=author)
        deck.save_white(new_card)
        return {
            'response_type': 'in_channel',
            'text': "New card: :white_square: _" + text + "_",
        }
    elif color == 'black':
        text = normalize_blanks(text)
        new_card = BlackCard(text=text, author=author)
        deck.save_black(new_card)
        return {
            'response_type': 'in_channel',
            'text': "New card: :black_square: _" + text + "_",
        }
    else:
        raise ValueError("Unknown card color!")

def handle_draw(deck):
    black_card = deck.draw_black()
    white_cards = deck.draw_whites(black_card.pick)
    return {
        'response_type': 'in_channel',
        'text': round_as_text(black_card, white_cards),
        'raw': round_as_dict(black_card, white_cards)
    }

def handler(req):

    params = util.FieldStorage(req, keep_blank_values=1)
    text = params['text']

    resp = {}

    try:
        deck = Deck(params['team_id'])
        author = User(id=params['user_id'], name=params['user_name'])

        if (text.startswith(black_emoji)):
            resp = handle_new_card('black', deck, author, remove_first_word(text))
        elif (text.startswith(white_emoji)):
            resp = handle_new_card('white', deck, author, remove_first_word(text))
        elif (text.startswith("status")):
            resp = handle_status(deck)
        elif (text is None or text == ""):
            resp = handle_draw(deck)
        else:
            resp = {
                'response_type': 'ephemerial',
                'text': "I don't understand that command."
            }
    except SlackError as e:
        resp = {
            'response_type': 'ephemerial',
            'text': str(e.value)
        }
    except Exception as e:
        resp = {
            'response_type': 'ephemerial',
            'text': ("Unexpected exception! " + str(e))
        }

    req.content_type = "application/json"
    req.write(json.dumps(resp))

    return apache.OK
