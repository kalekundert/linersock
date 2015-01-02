#!/usr/bin/env python

from __future__ import print_function

import threading, finalexam
from linersock import *
from linersock.test_helpers import *

forum_suite = finalexam.Suite("Testing the forums...")

# I accidentally created a bug that prevented any messages from being received
# over pipes, and it was not caught by any of these tests.  That's pretty
# fucked up.
#
# The bug was in the forum code that limits the number of messages received by
# the forum on any particular update cycle.  The greater-than sign was a less-
# than sign.

# The forum tests are something of a mess.  I just finished making a very
# simple change to the forum class that broke a lot of the tests, and it took
# me a long time to get the tests working again.  Most of that time was spent
# either trying to figure out how the tests were supposed to work or how to fit
# a simple change into the rigid existing scaffold.  

def setup(count):
    client_pipes, server_pipes = connect(count)

    servers = [(Forum(*server_pipes), Inbox())]
    clients = [(Forum(pipe), Inbox() ) for pipe in client_pipes]

    return servers, clients

def subscribe(flavor, forums):
    for forum, inbox in forums:
        forum.subscribe(flavor, inbox.receive)

def lock(forums):
    for forum, inbox in forums:
        forum.lock()

def publish(outbox, forums, flavor="default"):
    for forum, inbox in forums:
        message = outbox.send_message(flavor=flavor)
        forum.publish(message)

def update(servers, clients):
    for forum, inbox in clients + servers + clients:
        forum.update()

def check(outbox, forums, shuffled=False, empty=False):
    for forum, inbox in forums:
        inbox.check(outbox, shuffled, empty)


@forum_suite.test
def test_offline_forum(helper):
    forum = Forum()
    inbox, outbox = Inbox(), Outbox()

    publisher = forum.get_publisher()
    subscriber = forum.get_subscriber()

    flavor = outbox.flavor()
    message = outbox.send_message()

    subscriber.subscribe(flavor, inbox.receive)
    forum.lock()

    publisher.publish(message)
    forum.update()

    inbox.check(outbox)

@forum_suite.test
def test_online_forum(helper):
    server, clients = setup(4)

    outbox = Outbox()
    flavor = outbox.flavor()

    subscribe(flavor, clients)
    publish(outbox, server)

    lock(clients + server)

    update(server, clients)
    check(outbox, clients)

@forum_suite.test
def test_two_messages(helper):
    server, clients = setup(2)

    outbox = Outbox()
    flavor = outbox.flavor()

    subscribe(flavor, clients + server)
    lock(clients + server)

    publish(outbox, server)
    publish(outbox, server)

    update(server, clients)
    update(server, clients)

    check(outbox, clients + server)

@forum_suite.test
def test_shuffled_messages(helper):
    server, clients = setup(4)

    outbox = Outbox()
    flavor = outbox.flavor()

    subscribe(flavor, clients + server)
    lock(clients + server)

    for iteration in range(16):
        publish(outbox, clients)

    for iteration in range(4 * 16):
        update(server, clients)

    check(outbox, clients + server, shuffled=True)

@forum_suite.test
def test_unrelated_messages(helper):
    server, clients = setup(4)

    outbox = Outbox()
    related = outbox.flavor("first")
    unrelated = outbox.flavor("second")

    subscribe(related, clients + server)    # Related.
    lock(clients + server)

    for iteration in range(4):
        publish(outbox, clients, "second")    # Unrelated.

    for iteration in range(4):
        update(server, clients)

    # No messages should be received.
    outbox = Outbox()
    check(outbox, clients + server, empty=True)

@forum_suite.test
def test_different_messages(helper):
    server, clients = setup(8)
    groups = clients[:4], clients[4:]

    flavors = "first", "second"
    outboxes = Outbox(), Outbox()

    for group, outbox, flavor in zip(groups, outboxes, flavors):
        subscribe(outbox.flavor(flavor), group)

    lock(server + clients)

    for outbox, flavor in zip(outboxes, flavors):
        publish(outbox, server, flavor)

    for flavor in flavors:
        update(server, clients)

    for outbox, group in zip(outboxes, groups):
        check(outbox, group)


if __name__ == '__main__':
    finalexam.run(forum_suite)
