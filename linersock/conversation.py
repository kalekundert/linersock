class Conversation:
    """
    Manages a messaging system that allows two participants to carry out brief 
    conversations.  During the conversation, each participant can easily 
    transition back and forth between sending requests and waiting for 
    responses.  These transitions are configured in advance and played out 
    after the conversation starts.
    """
    
    def __init__(self, pipe, *exchanges):
        self.pipe = pipe
        self.exchanges = exchanges
        self.closed = False

    def get_pipe(self):
        return self.pipe

    def configure(self, *exchanges):
        self.exchanges += exchanges

    def start(self, *exchanges):
        self.pipe.lock()
        self.configure(*exchanges)

    def update(self):
        if not self.finished():
            self.update_outgoing()
            self.update_incoming()
            self.update_finished()

        return self.finished()

    def update_outgoing(self):
        for exchange in self.exchanges:
            message = exchange.send()
            if message is not None:
                self.pipe.send(message)

        self.pipe.deliver()
        self.update_exchanges()

    def update_incoming(self):
        for message in self.pipe.receive():
            for exchange in self.exchanges:
                exchange.receive(message)
            self.update_exchanges()

    def update_exchanges(self):
        self.exchanges = [ exchange.next()
                for exchange in self.exchanges
                if not exchange.finish() ]

    def update_finished(self):
        if not self.exchanges and self.pipe.idle():
            self.finish()

    def finish(self):
        self.pipe.unlock()
        self.exchanges = []
        self.closed = True

    def finished(self):
        return self.closed


class SimpleSend(Conversation):
    """
    Sends a single message and finishes without waiting for a response.
    This class is intended only for brief exchanges with SimpleReceive.  It 
    should not be used in more complex protocols.
    """

    def __init__(self, pipe, message):
        send = Send(message); finish = Finish()
        send.transition(finish)

        Conversation.__init__(self, pipe, send)


class SimpleReceive(Conversation):
    """
    Waits to receive a single message, then finishes.  This class is meant to 
    work with SimpleSend and should not be used in more complicated protocols.
    """

    def __init__(self, pipe, flavor, callback=lambda message: None):
        self.receive = Receive(); finish = Finish()
        self.receive.transition(finish, flavor, callback)

        Conversation.__init__(self, pipe, self.receive)

    def get_message(self):
        return self.receive.get_message()


class SimpleRequest(Conversation):
    """
    Sends a single message and waits to receive a response.  This class is can 
    be used in conjunction with SimpleResponse to request that information be 
    sent over the network.
    """

    def __init__(self, pipe, message, flavor, callback):
        request = Send(message)
        response = Receive()
        finish = Finish()

        request.transition(response)
        response.transition(finish, flavor, callback)

        Conversation.__init__(self, pipe, request)
        self.response = response

    def get_response(self):
        return self.response.get_message()


class SimpleResponse(Conversation):
    """
    Wait to receive a request, then respond with a predefined response.  This 
    exchange is specifically meant to be used with SimpleRequest.
    """

    def __init__(self, pipe, flavor, message):
        request = Receive()
        response = Send(message)
        finish = Finish()

        request.transition(response, flavor)
        request.transition(finish)

        Conversation.__init__(self, pipe, request)


class FullRequest(Conversation):
    """
    Sends a request and waits for it to either be accepted or rejected on the 
    other end.  This class is a wrapper around a conversation and a number of 
    different exchanges, meant to be useful in the most common situations.  If 
    you want to make a custom conversation, this may be useful to look at.
    """

    def __init__(self, pipe, message, accept_flavor, reject_flavor):

        # Begin by setting up all the exchanges that can happen on this side
        # of the conversation.  Once the request is sent, the conversation
        # will begin listening for a confirmation from its partner.  Once that
        # confirmation is received, the conversation ends and reports either
        # accept or reject, as appropriate.
        
        request = Send(message); reply = Receive()

        def accept_callback(): self.result = True
        def reject_callback(): self.result = False

        accept = Finish(accept_callback)
        reject = Finish(reject_callback)

        request.transition(reply)

        def save_response(message): self.response = message

        reply.transition(accept, accept_flavor, save_response)
        reply.transition(reject, reject_flavor, save_response)

        # Once the exchanges have been set up properly, create and store a
        # conversation object.  The second argument to the constructor
        # indicates that the conversation will begin by sending the request.

        Conversation.__init__(self, pipe, request)

        self.result = False
        self.response = None

    def get_accepted(self):
        assert self.finished()
        return self.finished() and self.result

    def get_rejected(self):
        assert self.finished()
        return self.finished() and not self.result

    def get_response(self):
        assert self.finished()
        return self.response


class FullResponse(Conversation):
    """
    Waits for a request to arrive and, once it does, decides whether or not to 
    accept it.  This class is meant to work with the request class above.  
    Normally the request will come from the client side and the response from 
    the server side.
    """

    def __init__(self, pipe, flavor_callback, accept_message, reject_message):

        # Begin by setting up all the exchanges that can happen on this side of
        # the conversation.  Once a request is received, it is evaluated using
        # the given callback.  If the callback returns True, the request is
        # accepted and the conversation is finished.  Otherwise, it is rejected
        # and another request is awaited.

        request = Receive(flavor_callback)

        accept = Send(accept_message)
        reject = Send(reject_message)

        def save_request(message): self.request = message

        request.transition(accept, True, save_request)
        request.transition(reject, False, save_request)

        finish = Finish()

        accept.transition(finish)
        reject.transition(request)

        Conversation.__init__(self, pipe, request)
        self.request = None

    def get_request(self):
        assert self.finished()
        return self.request



# The classes beyond this point are primarily intended for use within the
# classes above this point.  Some of these classes can still be used on their
# own, but are only necessary in unusual situations, while others should never
# be directly used.  Just be sure you know what you are doing.

class Exchange:
    """
    Represents a single exchange in a conversation.  The basic examples, which 
    are all implemented by subclasses below, include sending messages, 
    receiving messages, and ending the conversation.  Complex conversations can 
    be created by linking a number of these exchanges together.
    """
    
    def send(self):
        """
        Returns a message that should be sent to the other end of the 
        conversation.  Be careful, because this method will be called every 
        update cycle for as long as the exchange lasts.
        """
        return None

    def receive(self, message):
        """
        Accepts a message that was received from the other end of the 
        conversation.  The message is not necessarily relevant to this 
        exchange, but in many cases it will cause a transition to occur.
        """
        pass

    def next(self):
        """
        Returns the exchange that should be executed on the next update cycle.  
        To remain in the same exchange, return self.
        """
        raise NotImplementedError

    def finish(self):
        """
        Returns true if this side of the conversation is over.  The 
        conversation itself will keep updating until all outgoing and incoming 
        messages have been completely sent and received, respectively.
        """
        return False


class Send(Exchange):
    """
    Sends a message and immediately transitions to a different exchange.  That 
    exchange must be specified before the conversation starts.
    """

    def __init__(self, message):
        self.message = message
        self.exchange = None

    def send(self):
        return self.message

    def transition(self, exchange):
        self.exchange = exchange

    def next(self):
        return self.exchange


class Receive(Exchange):
    """
    Waits for a message to be received, then transitions the conversation to 
    another exchanges based on the content of the message.  Different types of 
    messages can cause different transitions.  The message type is the class of 
    the message by default, but this can be controlled by a callback.
    """

    def __init__(self, flavor=lambda message: type(message)):
        self.flavor = flavor

        # The received attribute contains the last message received, no matter
        # what its type is.  This allows receive() to communicate with next().

        self.received = None
        
        # The messages list contains all of the messages that were received and
        # recognized.  New messages are pushed onto the front of this list, so
        # the last message can be found at the 0th index.

        self.messages = []

        self.exchanges = {}
        self.callbacks = {}

    def get_message(self, index=0):
        return self.messages[index]

    def get_messages(self):
        return self.messages

    def receive(self, message):
        self.received = message

    def transition(self, exchange, flavor, callback=lambda message: None):
        self.exchanges[flavor] = exchange
        self.callbacks[flavor] = callback

    def next(self):
        message, self.received = self.received, None
        transition = self

        if message is not None:
            flavor = self.flavor(message)
            transition = self.exchanges.get(flavor, self)

        if transition is not self:
            self.callbacks[flavor](message)
            self.messages.insert(0, message)
        
        return transition


class Finish(Exchange):
    """
    Ends the conversation without sending or receiving anything.  Note that 
    this does not end the conversation running on the far side of the 
    connection.
    """

    def __init__(self, callback=lambda: None):
        self.callback = callback

    def finish(self):
        self.callback()
        return True


