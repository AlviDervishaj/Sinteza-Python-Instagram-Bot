from GramAddict.core.plugin_loader import Plugin

# Not really a plugin, but didn't want to add the parameter to core


class ClonedApp(Plugin):
    """Adds support for cloned apps"""

    def __init__(self):
        super().__init__()
        self.description = "Adds support for cloned apps"
        self.arguments = [
            {
                "arg": "--app-id",
                "nargs": None,
                "help": "provide app-id if using a custom/cloned app",
                "metavar": "com.instagram.android",
                "default": "com.instagram.android",
            },
            {
                "arg": "--cloned-app-mode",
                "nargs": None,
                "help": "use the cloned app instead the official, has several mode",
                "metavar": 1,
                "default": 0,
            },
        ]
