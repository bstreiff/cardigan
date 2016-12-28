#!/usr/bin/python
# -*- coding: utf_8 -*-
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
import re
import sqlite3

db_path = "/var/lib/www/cah"

blank_pattern = u":blank:"
black_emoji = (u":black_square:", u":black_small_square:", u":black_medium_small_square:",
               u":black_medium_square:", u":black_large_square:", u":black_circle:", u"black")
white_emoji = (u":white_square:", u":white_small_square:", u":white_medium_small_square:",
               u":white_medium_square:", u":white_large_square:", u":white_circle:", u"white")

class SlackError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def bold(string):
    return u"*{0}*".format(string)

def italic(string):
    return u"_{0}_".format(string)

def base_response(type, text):
    response = {
        'response_type': type,
        'text': text,
    }
    return response

def ephemeral_response(text):
    return base_response('ephemeral', text)

def channel_response(text):
    return base_response('in_channel', text)

def conjoin(ary):
    if (len(ary) == 0):
        return u""
    elif (len(ary) == 1):
        return u"{0}".format(ary[0])
    elif (len(ary) == 2):
        return u"{0} and {1}".format(ary[0], ary[1])
    else:
        return u"{0}, and {1}".format(
                                ", ".join(ary[0:-1]),
                                ary[-1])

def remove_first_word(text):
    first, _, rest = text.partition(" ")
    return rest or first

def uppercase_first(text):
    if (len == 0):
        return text
    else:
        if (text[0] == u"*"):
            return text[0] + text[1].upper() + text[2:]
        else:
            return text[0].upper() + text[1:]

def round_as_text(black_card, white_cards):
    text = black_card.text
    top_card = 0;

    while (text.count(blank_pattern) > 0):
        answer = bold(white_cards[top_card].text)
        top_card += 1
        text = text.replace(blank_pattern, answer, 1);

    # If cards left over, then the end is implied to be a blank.
    if (top_card < len(white_cards)):
        text = text + " " + conjoin([ bold(c.text) for c in white_cards[top_card:] ]) + "."

    return uppercase_first(text)

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

class Card:
    def __init__(self, text, author=None, card_id=None):
        self.text = text
        self.author = author
        self.card_id = card_id

    def get_id_str(self):
        return self.ID_PREFIX+str(self.card_id)

class BlackCard(Card):
    TABLE = u"black_cards"
    ID_PREFIX = u"B"
    EMOJI = u":black_square:"

    def __init__(self, text, author=None, card_id=None):
        Card.__init__(self, text, author, card_id)

    def get_pick_count(self):
        appears = self.text.count(blank_pattern)
        if (appears == 0):
            return 1
        else:
            return appears

    def get_draw_count(self):
        pick = self.get_pick_count()
        if pick >= 3:
            self.draw = pick - 1
        else:
            self.draw = 0

    def as_dict(self):
        return { 'text': self.text,
                 'draw': self.get_draw_count(),
                 'pick': self.get_pick_count(),
                 'card_id': self.card_id }

class WhiteCard(Card):
    TABLE = u"white_cards"
    ID_PREFIX = u"W"
    EMOJI = u":white_square:"

    def as_dict(self):
        return { 'text': self.text,
                 'card_id': self.card_id }

def is_valid_id(text):
    pattern = re.compile("^([A-Za-z0-9])+$")
    return pattern.match(text)

class DeckStatus:
    def __init__(self, black_card_count, white_card_count, authors):
        self.black_card_count = black_card_count
        self.white_card_count = white_card_count
        self.authors = authors;

class Deck:
    BLACK_SELECT = u"select text, user_id, user_name, id from black_cards"
    WHITE_SELECT = u"select text, user_id, user_name, id from white_cards"
    BLACK_INSERT = u"insert or replace into black_cards (id, text, user_id, user_name) values (?,?,?,?)"
    WHITE_INSERT = u"insert or replace into white_cards (id, text, user_id, user_name) values (?,?,?,?)"

    def __init__(self, deck_name):
        if not is_valid_id(deck_name):
            raise ValueError("bad deck name")

        self.connection = sqlite3.connect(db_path + "/" + deck_name + "-cards.db")

        self.connection.execute(
            u"create table if not exists config ("
            u"	name        varchar unique primary key,"
            u"	value       varchar  "
            u")")

        self.connection.execute(
            u"create table if not exists black_cards ("
            u"	id          integer primary key,"
            u"	text        varchar, "
            u"	user_id     varchar, "
            u"	user_name   varchar  "
            u")")
        self.connection.execute(
            u"create table if not exists white_cards ("
            u"	id          integer primary key, "
            u"	text        varchar, "
            u"	user_id     varchar, "
            u"	user_name   varchar  "
            u")")

    def get_config_item(self, name):
        cursor = self.connection.cursor()
        cursor.execute(u"select value from config where name=?", (name,))
        value = None
        for row in cursor:
            value = row[0]
        return value

    def set_config_item(self, name, value):
        cursor = self.connection.cursor()
        cursor.execute(u"insert or replace into config (name, value) values (?,?)", (name, value))
        self.connection.commit()

    def __draw(self, table, count, processor):
        cursor = self.connection.cursor()
        # "ORDER BY RANDOM() LIMIT 1" isn't good for performance,
        # but my thought is that the sample size will be low enough
        # that I'm choosing not to worry about this now.
        cursor.execute(u"select text, user_id, user_name, id from "+table+u" order by RANDOM() limit ?", str(count))
        result = processor(cursor);
        if (len(result) != count):
            raise SlackError(u"Not enough cards!")
        return result

    def draw_black(self):
        return self.__draw(u"black_cards", 1, self.__cursor_to_black_cards)[0]

    def draw_whites(self, count=1):
        return self.__draw(u"white_cards", count, self.__cursor_to_white_cards)

    def __find_existing(self, table, text):
        cursor = self.connection.cursor()
        cursor.execute(u"select id from "+table+u" where upper(text)=upper(?)", (text,))
        row = cursor.fetchone()
        if (row is None):
            return None
        else:
            return row[0]

    def save(self, card):
        existing_id = self.__find_existing(card.TABLE, card.text)
        if (not existing_id is None and existing_id != card.card_id):
            raise SlackError(u"Card already exists (as {0}{1}).".format(card.ID_PREFIX, existing_id))

        cursor = self.connection.cursor()
        cursor.execute(u"insert or replace into "+card.TABLE+" (id, text, user_id, user_name) values (?,?,?,?)", (
                           card.card_id,
                           card.text,
                           card.author.id,
                           card.author.name))
        card.card_id = cursor.lastrowid
        self.connection.commit()
        return card.card_id

    def get_status(self):
        cursor = self.connection.cursor()
        cursor.execute(u"select count(*) from white_cards");
        white_card_count = cursor.fetchone()[0]
        cursor.execute(u"select count(*) from black_cards");
        black_card_count = cursor.fetchone()[0]

        authors = {}
        cursor.execute(u"select user_name, count(*) from black_cards group by user_id");
        for row in cursor:
            (user_name, count) = row
            if (not user_name in authors):
                authors[user_name] = {'black':0,'white':0}
            authors[user_name]['black'] = count;
        cursor.execute(u"select user_name, count(*) from white_cards group by user_id");
        for row in cursor:
            (user_name, count) = row
            if (not user_name in authors):
                authors[user_name] = {'black':0,'white':0}
            authors[user_name]['white'] = count;

        return DeckStatus(white_card_count=white_card_count,
                          black_card_count=black_card_count,
                          authors=authors)

    def get_black_card(self, numeric_id):
        cursor = self.connection.cursor()
        cursor.execute(Deck.BLACK_SELECT + u" where id=?", (numeric_id,))
        results = self.__cursor_to_black_cards(cursor)
        if (len(results) < 1):
            return None
        else:
            return results[0]

    def get_white_card(self, numeric_id):
        cursor = self.connection.cursor()
        cursor.execute(Deck.WHITE_SELECT + u" where id=?", (numeric_id,))
        results = self.__cursor_to_white_cards(cursor)
        if (len(results) < 1):
            return None
        else:
            return results[0]

    def get_card_by_id(self, card_id):
        if (card_id is None or card_id == u""):
            raise SlackError(u"Card id was empty.")
        pattern = re.compile("^([BW])([0-9]+)$")
        card_id = card_id.upper()
        match = pattern.match(card_id)
        if not match:
            raise SlackError(u"Invalid card id '{0}'".format(card_id))

        if (match.group(1) == 'B'):
            card = self.get_black_card(int(match.group(2)))
        else:
            card = self.get_white_card(int(match.group(2)))

        if not card:
            raise SlackError(u"Card '{0}' not found.".format(card_id))
        else:
            return card

    def __cursor_to_white_cards(self, cursor):
        results = []
        for row in cursor:
            (text, user_id, user_name, card_id) = row
            results.append(WhiteCard(text=text,
                                     author=User(id=user_id, name=user_name),
                                     card_id=card_id))
        return results

    def __cursor_to_black_cards(self, cursor):
        results = []
        for row in cursor:
            (text, user_id, user_name, card_id) = row
            results.append(BlackCard(text=text,
                                     author=User(id=user_id, name=user_name),
                                     card_id=card_id))
        return results

    def search(self, text):
        text = "%" + text + "%"
        cursor = self.connection.cursor()
        cards = [];
        cursor.execute(Deck.BLACK_SELECT + u" where text like ?", (text,));
        cards += self.__cursor_to_black_cards(cursor);
        cursor.execute(Deck.WHITE_SELECT + u" where text like ?", (text,));
        cards += self.__cursor_to_white_cards(cursor);
        return cards

def handle_status(deck):
    status = deck.get_status()

    reply = u"Total cards: :white_square:{0} :black_square:{1}".format(
        status.white_card_count, status.black_card_count);

    # Get a list of (count,name) tuples sorted by total card count
    authors_sorted = sorted(
                        [ (x[1]['black']+x[1]['white'], x[0]) for x in status.authors.items() ],
                        reverse=True);

    fields = []

    # Render as a string.
    for author in authors_sorted:
        fields.append({
            "value": u"{0}: :white_square:{1} :black_square:{2}".format(
                author[1],
                status.authors[author[1]]['white'],
                status.authors[author[1]]['black']),
            "short": True
        })

    return {
        'response_type': 'in_channel',
        'text': reply,
        'attachments': [
            {
                'fields': fields
            }
        ]
    };


def handle_new_card(color, deck, author, text):
    text = normalize_blanks(text)
    if color == 'white':
        new_card = WhiteCard(text=text, author=author)
    elif color == 'black':
        new_card = BlackCard(text=text, author=author)
    else:
        raise ValueError("Unknown card color!")

    deck.save(new_card)
    reply = u"New card: ({0}) {1} {2}".format(
                new_card.get_id_str(),
                new_card.EMOJI,
                italic(text))

    return channel_response(reply)

def handle_draw(deck):
    black_card = deck.draw_black()
    white_cards = deck.draw_whites(black_card.get_pick_count())
    return {
        'response_type': 'in_channel',
        'text': round_as_text(black_card, white_cards),
        'raw': round_as_dict(black_card, white_cards)
    }

def handle_deal(deck, text):
    ids = text.split()
    if (len(ids) == 0):
        raise SlackError(u"Usage: deal <id> [<id> ...]");

    first = deck.get_card_by_id(ids[0])
    # If the first card is black, then we use that.
    # Otherwise, the black card is chosen at random.
    if (first.ID_PREFIX == "B"):
        black_card = first;
        ids.pop(0)
    else:
        black_card = deck.draw_black();

    # The rest of the list needs to contain only white cards.
    cards_needed = black_card.get_pick_count();
    # Only use as many cards as we need.
    white_cards = []
    for id in ids:
        white_cards.append(deck.get_card_by_id(id))
    # Not enough? Draw some more.
    if (len(white_cards) < cards_needed):
        white_cards += deck.draw_whites(cards_needed-len(white_cards))

    return {
        'response_type': 'in_channel',
        'text': round_as_text(black_card, white_cards)
    }

def handle_search(deck, text):
    cards = deck.search(text)

    if (len(cards) == 0):
        return ephemeral_response(
            u"No results found for {0}".format(italic(text)))

    total_count = len(cards)
    result_cap = 4
    card_strings = [ u"({}) {}".format(c.get_id_str(), c.text) for c in cards ]

    if (total_count > result_cap):
        card_strings = card_strings[0:result_cap]
        returned_count = len(card_strings)
        card_strings.append(u"... and more. Please be more specific.");
    else:
        returned_count = len(card_strings)

    attachmentText = "\n".join(card_strings)

    return {
        'response_type': 'ephemeral',
        'text': u"Search for {0} ({1} of {2} results)".format(
                    italic(text),
                    returned_count,
                    total_count),
        'attachments': [
            {
                'text': attachmentText
            }
        ]
    };

def handle_edit(deck, text):
    (card_id, _, rest) = text.partition(" ")
    rest = rest.strip();
    if (len(rest) == 0):
        raise SlackError(u"Need to have a phrase to edit to.")
    newtext = normalize_blanks(rest)

    card = deck.get_card_by_id(card_id)
    oldtext = card.text
    if (newtext == oldtext):
        raise SlackError(u"New text same as old text, no change necessary.")

    card.text = newtext
    deck.save(card)

    reply = u"Card: ({0}) Was: {1}, Now: {2}".format(
                card.get_id_str(),
                italic(oldtext),
                italic(newtext))

    return channel_response(reply)

def handle_help(argv0):
    return {
        'response_type': 'ephemeral',
        'text': ("*Help for "+argv0+"*:\n" +
                 "`"+argv0+"` - Generate a new phrase\n" +
                 "`"+argv0+" white <text>` - Add a new white card\n" +
                 "`"+argv0+" black <text>` - Add a new black card; use `:blank:` or at least 3 underscores for blanks.\n" +
                 "`"+argv0+" search <str>` - Find cards with 'str'\n" +
                 "`"+argv0+" edit <id> <text>` - Edit an existing card\n" +
                 "`"+argv0+" deal <id> [<id> ...]` - Deal specific cards\n" +
                 "`"+argv0+" status` - Database info\n" +
                 "`"+argv0+" help` - This text")
    }

def handler(req):

    params = util.FieldStorage(req, keep_blank_values=1)

    resp = {}
    try:
        if (not "text" in params):
            raise SlackError(u"Bad request: No text given.")
        if (not "team_id" in params):
            raise SlackError(u"Bad request: No team_id given.")
        if (not "user_id" in params):
            raise SlackError(u"Bad request: No user_id given.")
        if (not "user_name" in params):
            raise SlackError(u"Bad request: No user_name given.")
        if (not "command" in params):
            raise SlackError(u"Bad request: No command given.")

        # Incoming data is application/x-www-form-urlencoded. We
        # assume that it's UTF-8 encoded. There does not appear to
        # be a header or anything we can check to confirm, so we
        # just blindly convert.
        text = params['text'].decode('utf-8')
        deck = Deck(params['team_id'].decode('utf-8'))
        author = User(id=params['user_id'].decode('utf-8'),
                      name=params['user_name'].decode('utf-8'))
        command = params['command'].decode('utf-8')

        read_only = False;

        # Check that token matches.
        # If this is the first time, set it.
        # If the token doesn't match, we're read-only.
        token = params['token'].decode('utf-8')
        db_token = deck.get_config_item("token")
        if not db_token:
            deck.set_config_item("token", token)
        elif (db_token != token):
            read_only = True;

        cmd = text.lower()

        if (cmd.startswith(u"help")):
            resp = handle_help(command)
        elif (cmd.startswith(black_emoji) and not read_only):
            resp = handle_new_card(u"black", deck, author, remove_first_word(text))
        elif (cmd.startswith(white_emoji) and not read_only):
            resp = handle_new_card(u"white", deck, author, remove_first_word(text))
        elif (cmd.startswith(u"status")):
            resp = handle_status(deck)
        elif (cmd.startswith(u"search")):
            resp = handle_search(deck, remove_first_word(text))
        elif (cmd.startswith(u"edit") and not read_only):
            resp = handle_edit(deck, remove_first_word(text))
        elif (cmd.startswith(u"deal")):
            resp = handle_deal(deck, remove_first_word(text))
        elif (text is None or text == u""):
            resp = handle_draw(deck)
        else:
            resp = ephemeral_response(u"I don't understand that command.")
    except SlackError as e:
        resp = ephemeral_response(str(e.value))
    except Exception as e:
        resp = ephemeral_response(
                    ("Unexpected exception! " + str(e)))

    req.content_type = "application/json; charset=utf-8"
    req.write(json.dumps(resp))

    return apache.OK
