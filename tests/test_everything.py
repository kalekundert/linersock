#!/usr/bin/env python

import sys, finalexam
import test_pipes, test_forums, test_conversations

finalexam.run(
        test_pipes.wrapper_suite,
        test_forums.forum_suite,
        test_conversations.conversation_suite,
        test_conversations.request_response_suite,
)

