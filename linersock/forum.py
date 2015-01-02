import six
from six.moves import queue

class Forum:
    """
    Manages a messaging system that allows messages to be published for any 
    interested subscriber to receive.  If desired, published messages will even 
    be delivered across a network.  Furthermore, since the system was designed 
    to work with concurrent applications, messages can be safely published at 
    any time from any thread.
    """

    def __init__(self, *pipes, **options):
        """
        Create and prepare a new forum object.  If any network connections are 
        passed into the constructor, the forum will presume that other forums 
        are listening and will attempt to communicate with them.
        """
        self.pipes = []
        self.locked = False

        self.subscriptions = {}
        self.publications = queue.Queue()

        safety_flag = options.get('safe', True)

        self.incoming_limit = 1 if safety_flag else float('inf')
        self.incoming_publications = []

        class Publisher:
            publish = self.publish

        class Subscriber:
            subscribe = self.subscribe

        class Member:
            publish = self.publish
            subscribe = self.subscribe

        self.publisher = Publisher()
        self.subscriber = Subscriber()
        self.member = Member()

        self.setup(*pipes)

    def subscribe(self, flavor, callback):
        """
        Attach a callback to a particular flavor of message.  For simplicity, 
        the message's flavor is always the message's class.  This requires that 
        all messages be instances of new-style classes.  Once the forum is 
        locked, new subscriptions can no longer be made.
        """
        assert not self.locked

        try:
            self.subscriptions[flavor].append(callback)
        except KeyError:
            self.subscriptions[flavor] = [callback]

    def publish(self, message, callback=lambda: None):
        """
        Publish the given message so subscribers to that class of message can 
        react to it.  If any remote forums are connected, the underlying 
        network connection must be capable of serializing the message.
        """

        publication = Publication(message, receipt=callback)
        self.publications.put(publication)

    def setup(self, *pipes):
        """
        Connect this forum to another forum on a remote machine.  Any message 
        published by either forum will be relayed to the other.  This method 
        must be called before the forum is locked.
        """

        assert not self.locked
        self.pipes.extend(pipes)

    def update(self):
        """
        Deliver any messages that have been published since the last call to 
        this function.  For local messages, this requires executing the proper 
        callback for each subscriber.  For remote messages, this involves both 
        checking for incoming packets and relaying new publications across the 
        network.  No publications can be delivered before the forum is locked.
        """

        assert self.locked

        # Accept any messages that came in over the network since the last
        # update.  Not all of these messages will necessarily delivered this
        # time.  Those that aren't will be stored and delivered later.
        
        for pipe in self.pipes:
            for message in pipe.receive():
                publication = Publication(message, origin=pipe)
                self.incoming_publications.append(publication)

        # Decide how many messages to deliver.  It is safer to deliver only
        # one, because this eliminates some potential race conditions.
        # However, sometimes this performance hit is unacceptable.

        iteration = 0
        while True:
            iteration += 1

            if iteration > self.incoming_limit:
                break
            if not self.incoming_publications:
                break

            publication = self.incoming_publications.pop(0)
            self.publications.put(publication)

        # Pop messages off the publication queue one at a time.

        while True:
            try: 
                publication = self.publications.get(False)

                # Deliver the message to local subscribers.

                message = publication.message
                flavor = type(message)

                for callback in self.subscriptions.get(flavor, []):
                    callback(message)

                # Deliver the message to any remote peers.

                for pipe in self.pipes:
                    if pipe is not publication.origin:
                        pipe.send(message, publication.receipt)

            except queue.Empty:
                break

        # Send any queued up outgoing messages.

        for pipe in self.pipes:
            for receipt in pipe.deliver():
                
                # Deliver returns a list of receipt objects for each message
                # that is successfully sent.  The forum makes sure that all of
                # these receipts are callbacks.

                receipt()

    def teardown(self):
        """
        Prevent the forum from being used anymore.  This is exactly equivalent 
        to calling unlock.
        """
        self.unlock()

    def lock(self):
        """
        Prevent the forum from making any more subscriptions and allow it to 
        begin delivering publications.
        """

        self.locked = True

        for pipe in self.pipes:
            pipe.lock()

    def unlock(self):
        """
        Prevent the forum from delivering messages and allow it to make new 
        subscriptions.  All existing subscriptions are cleared.
        """

        self.locked = False

        self.subscriptions = {}
        self.publications = queue.Queue()

        for pipe in self.pipes:
            pipe.unlock()


    def get_member(self):
        return self.member

    def get_publisher(self):
        return self.publisher

    def get_subscriber(self):
        return self.subscriber


class Publication:
    """
    Represents messages that are waiting to be delivered within a forum.
    Outside of the forum, this class should never be used.
    """

    # The origin argument specifies the pipe that delivered this publication.
    # It is used to avoid returning a incoming message to the forum that
    # originally sent it.  For new publications, this field isn't important and
    # should not be specified.
    #
    # The receipt argument specifies a callback which will be executed
    # once the message in question is delivered.  This is only meaningful for
    # messages that originated in this forum.

    def __init__(self, message, origin=None, receipt=lambda: None):
        self.message = message
        self.origin = origin
        self.receipt = receipt


