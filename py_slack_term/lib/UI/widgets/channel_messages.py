import curses
import re

import npyscreen
from npyscreen.wgmultiline import MORE_LABEL

from py_slack_term.lib.slack_client.RTM.rtmclient import TypingUserWatchdogThread
from ....lib.slack_client.API import Channel, Message


class ChannelMessages(npyscreen.BufferPager):
    message_format = "{user}: {text}"
    mention_regex = re.compile("<@[A-Z0-9]+>")

    def __init__(self, *args, **kwargs):
        super(ChannelMessages, self).__init__(*args, **kwargs)
        self.autowrap = True

    def display_value(self, vl: Message) -> str:
        if isinstance(vl, Message):
            message_dict = vl.to_format_dict()
            text = str(message_dict.get('text'))
            if text is not None:
                match = re.search(self.mention_regex, text)
                if match:
                    # replace the <@XXXXXX> decorations, and leave only the user id
                    user_id = match.group().replace('<', '').replace('@', '').replace('>', '')
                    # replace userid with an '@' annotated username
                    message_dict['text'] = message_dict.get('text').replace(match.group(),
                                                                        '@' + vl.client.users.get(user_id).get_name())
                text = self.message_format.format(**message_dict)
        # there should only be Message objects passed into here, SOMEHOW we sometimes dont get one
        # or its 'text' attribute is "none"
        # TODO: this is a hack, needs investigation
        else:
            text = str(vl)
        return text

    def clear_buffer(self, *args, **kwargs):
        """
        compatibility with non pythonic code in library
        """
        self.clearBuffer(*args, **kwargs)

    # TODO: this is a monkey patch of the base class Pager
    # TODO: this method can be removed when https://github.com/npcole/npyscreen/pull/60 is merged
    def update(self, clear=True):
        #we look this up a lot. Let's have it here.
        if self.autowrap:
            # this is the patch     V----------------------------V
            self.setValuesWrap(list(self.display_value(l) for l in self.values))

        if self.center:
            self.centerValues()

        display_length = len(self._my_widgets)
        values_len = len(self.values)

        if self.start_display_at > values_len - display_length:
            self.start_display_at = values_len - display_length
        if self.start_display_at < 0:
            self.start_display_at = 0

        indexer = 0 + self.start_display_at
        for line in self._my_widgets[:-1]:
            self._print_line(line, indexer)
            indexer += 1

        # Now do the final line
        line = self._my_widgets[-1]

        if values_len <= indexer+1:
            self._print_line(line, indexer)
        else:
            line.value = MORE_LABEL
            line.highlight = False
            line.show_bold = False

        for w in self._my_widgets:
            # call update to avoid needless refreshes
            w.update(clear=True)
        # There is a bug somewhere that affects the first line.  This cures it.
        # Without this line, the first line inherits the color of the form when not editing. Not clear why.
        self._my_widgets[0].update()

    def set_up_handlers(self):
        super(ChannelMessages, self).set_up_handlers()
        self.handlers.update({
            curses.KEY_LEFT: self.h_exit_left,
            curses.KEY_RIGHT: self.h_exit_right
        })


class BoxedChannelMessages(npyscreen.BoxTitle):
    _contained_widget = ChannelMessages

    def __init__(self, *args, **kwargs):
        self.name = 'Messages'
        super(BoxedChannelMessages, self).__init__(*args, **kwargs)
        self.current_channel = None
        self.typing_user_watchdog_thread = TypingUserWatchdogThread(widget=self)

    def buffer(self, *args, **kwargs) -> None:
        self.entry_widget.buffer(*args, **kwargs)
        self.display()

    def clear_buffer(self, *args, **kwargs) -> None:
        self.entry_widget.clear_buffer(*args, **kwargs)

    def set_channel(self, ch: Channel) -> None:
        """
        function to set title of box to channel name and display associated information
        """
        if ch is not None:
            self.current_channel = ch

        new_name = "Messages | {name}".format(name=ch.name)

        if ch.topic:
            topic = ch.topic.get('value')
        elif ch.purpose:
            topic = ch.purpose.get('value')
        else:
            topic = None
        if topic:
            new_name += " ({})".format(topic)

        if ch.is_private:
            new_name += " [PRIVATE]"

        self.name = new_name
        self.typing_user_watchdog_thread.start()

    def typing_user_event(self):
        try:
            typing_users = [u.get_name() for u in self.current_channel.typing_users.keys()]
        except:
            typing_users = []

        if len(typing_users) < 1:
            self.footer = None
        elif len(typing_users) == 1:
            self.footer = '{} is typing...'.format(typing_users[0])
        elif len(typing_users) < 4:
            self.footer = '{} and {} are typing...'.format(', '.join(typing_users[:-1]), typing_users[-1])
        elif len(typing_users) >= 4:
            self.footer = 'Multiple people are typing...'
        self.display()

    def destroy(self):
        self.typing_user_watchdog_thread.stop()
        super(BoxedChannelMessages, self).destroy()


