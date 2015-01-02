#!/usr/bin/env python

from __future__ import print_function

import threading, finalexam
from linersock import *
from linersock.test_helpers import *

conversation_suite = finalexam.Suite("Testing the conversations...")
request_response_suite = finalexam.Suite("Testing requests and responses...")

@conversation_suite.setup
def conversation_setup(helper):
    helper.pipes = client, server = connect()

    helper.client = Conversation(client)
    helper.server = Conversation(server)
    helper.conversations = helper.client, helper.server

    helper.inbox = Inbox()
    helper.outbox = Outbox()
    helper.boxes = helper.inbox, helper.outbox

    helper.message = helper.outbox.message()
    helper.flavor = helper.outbox.flavor()
    helper.outgoing = helper.message, helper.flavor

    helper.finish = Finish()

    def configure(*exchanges):
        iterator = zip(helper.conversations, exchanges)
        for conversation, exchange in iterator:
            conversation.configure(exchange)

    def run(*exchanges):
        helper.configure(*exchanges)
        list = helper.conversations

        for conversation in list:
            conversation.start()

        while list:
            list = [ conversation for conversation in list
                    if not conversation.finished() ]

            for conversation in list:
                conversation.update()

    def check(inbox=helper.inbox, outbox=helper.outbox,
            shuffled=False, empty=False):
        inbox.check(outbox, shuffled, empty)


    helper.configure = configure
    helper.run = run
    helper.check = check

@conversation_suite.teardown
def conversation_teardown(helper):
    disconnect(*helper.pipes)


@conversation_suite.test
def test_one_message(helper):
    inbox, outbox = helper.boxes
    message, flavor = helper.outgoing

    request = Send(message)
    request.transition(helper.finish)

    reply = Receive()
    reply.transition(helper.finish, flavor, inbox.receive)

    outbox.send(message)

    helper.run(request, reply)
    helper.check()

@conversation_suite.test
def test_two_messages(helper):
    inbox, outbox = helper.boxes
    message, flavor = helper.outgoing

    request_1 = Send(message)
    request_2 = Send(message)

    request_1.transition(request_2)
    request_2.transition(helper.finish)

    reply_1 = Receive()
    reply_2 = Receive()

    reply_1.transition(reply_2, flavor, inbox.receive)
    reply_2.transition(helper.finish, flavor, inbox.receive)

    outbox.send(message)
    outbox.send(message)

    helper.run(request_1, reply_1)
    helper.check()

@conversation_suite.test
def test_ignore_extra_messages(helper):
    inbox, outbox = helper.boxes
    message, flavor = helper.outgoing

    # This setup will cause the same request to be sent twice, because the
    # first request transitions into the second one.  However, only one message
    # should be received because only one message is being listened for.

    request_1 = Send(message)
    request_2 = Send(message)

    request_1.transition(request_2)
    request_2.transition(helper.finish)

    only_reply = Receive()
    only_reply.transition(helper.finish, flavor, inbox.receive)

    outbox.send(message)

    helper.run(request_1, only_reply)
    helper.check()

@conversation_suite.test
def test_simultaneous_exchanges(helper):
    inbox, outbox = helper.boxes
    message, flavor = helper.outgoing

    # In this test, both the client and the server are simultaneously sending
    # and receiving messages of the same type.  Each side sends only one
    # message, but I expect to end up with two messages because I am sharing
    # the inbox.

    client_request, server_request = Send(message), Send(message)
    client_reply, server_reply = Receive(), Receive()

    client_request.transition(helper.finish)
    server_request.transition(helper.finish)

    client_reply.transition(helper.finish, flavor, inbox.receive)
    server_reply.transition(helper.finish, flavor, inbox.receive)

    outbox.send(message)
    outbox.send(message)

    helper.configure(client_request, server_request)
    helper.configure(client_reply, server_reply)

    helper.run()
    helper.check()


@request_response_suite.setup
def request_response_setup(helper):
    client, server = helper.pipes = connect()
    outbox = Outbox()

    request_message = outbox.message(flavor="first")
    request_flavor = outbox.flavor(flavor="first")

    accept_message = outbox.message(flavor="second")
    accept_flavor = outbox.flavor(flavor="second")

    reject_message = outbox.message(flavor="third")
    reject_flavor = outbox.flavor(flavor="third")

    print("Request Message:", request_message)
    print("Accept Message:", accept_message)
    print("Reject Message:", reject_message)
    print()

    class decision_callback(object):

        def __init__(self, pattern):
            self.pattern = list(pattern)

        def __str__(self):
            decision = "accept" if self.pattern[0] else "reject"
            return "Deciding to %s message.\n" % decision

        def __call__(self, message):
            print(self)
            return self.pattern.pop(0)

    def request():
        request = FullRequest(client,
                request_message, accept_flavor, reject_flavor)

        request.start()
        return request

    def response(*pattern):
        assert pattern
        helper.expected = pattern

        response = FullResponse(server,
                decision_callback(pattern), accept_message, reject_message)

        response.start()
        return response

    def update(request, response):
        while not request.finished():
            for conversation in (request, response):
                if not conversation.finished():
                    conversation.update()

    def finished(request, response):
        for conversation in (request, response):
            if not conversation.finished():
                return False
            return True

    def check(request, response, accepted=True):
        if accepted:
            assert request.get_accepted() == True
            assert request.get_rejected() == False

            assert request.get_response() == accept_message
            assert response.get_request() == request_message

        else:
            assert request.get_rejected() == True
            assert request.get_accepted() == False
            assert request.get_response() == reject_message


    helper.request = request
    helper.response = response

    helper.update = update
    helper.finished = finished
    helper.check = check

@request_response_suite.teardown
def request_response_teardown(helper):
    disconnect(*helper.pipes)


@request_response_suite.test
def test_accept_request(helper):
    request = helper.request()
    response = helper.response(True)

    helper.update(request, response)
    helper.check(request, response)

@request_response_suite.test
def test_reject_request(helper):
    request = helper.request()
    response = helper.response(False, False, True)

    # The response() factory function copies the pattern of expected results
    # into the 'expected' variable, so that loops like this are possible.

    for expected in helper.expected:
        helper.update(request, response)
        helper.check(request, response, expected)

        if not expected:
            request = helper.request()


if __name__ == '__main__':
    finalexam.run(conversation_suite, request_response_suite)

