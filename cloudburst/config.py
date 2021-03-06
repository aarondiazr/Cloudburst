from ConfigParser import SafeConfigParser


class Config():

    __CONFIG_FILE = 'config.ini'

    __config_loaded = False

    __config_dictionary = {}
    __config_parser = SafeConfigParser()

    @staticmethod
    def set_general_option(option, value):
        """ Set an option in the general section """
        Config._load_config()
        Config._set('general', option, value)

    @staticmethod
    def set_torrent_option(option, value):
        """ Set an option in the torrent section """
        Config._load_config()
        Config._set('torrent', option, value)

    @staticmethod
    def set_video_option(option, value):
        """ Set an option in the video section """
        Config._load_config()
        Config._set('video', option, value)

    # ADD MORE SECTIONS HERE





    @staticmethod
    def option_exists(section, option):
        """ Returns True if the option exists in the specified section """
        Config._load_config()
        return Config.__config_parser.has_option(section, option)

    @staticmethod
    def getboolean(section, option):
        """ Get a boolean from the specified section """
        Config._load_config()
        return Config.__config_parser.getboolean(section, option)

    @staticmethod
    def getint(section, option):
        """ Get an int from the specified section """
        Config._load_config()
        return Config.__config_parser.getint(section, option)

    @staticmethod
    def getfloat(section, option):
        """ Get a float from the specified section """
        Config._load_config()
        return Config.__config_parser.getfloat(section, option)

    @staticmethod
    def getstring(section, option):
        """ Get a string from the specified section """
        Config._load_config()
        return Config.__config_parser.get(section, option)


    # Internal functions

    @staticmethod
    def _load_config():
        """ Loads the config file from disk into the config_parses object """
        if not Config.__config_loaded:
            Config.__config_loaded = True

            # Load the config file into the config_parses object
            try:
                with Config._open_config_file(read=True) as config_file:
                    Config.__config_parser.readfp(fp=config_file)
            except IOError:
                pass    # File does not exist, do not load it but don't create it either (what use is an empty file?)

    @staticmethod
    def _open_config_file(read=False, write=False):
        """ Open the config file for reading and/or writing """
        mode = ''
        if read: mode += 'r'
        if write: mode += 'w'

        return open(Config.__CONFIG_FILE, mode)

    @staticmethod
    def _write_config():
        """ Open the config file and write the config parses contents """
        with Config._open_config_file(write=True) as fp:
            Config.__config_parser.write(fp)

    @staticmethod
    def _set(section, option, value):
        """ Set an option in a specified section and write it to disk """
        if not Config.__config_parser.has_section(section):
            Config.__config_parser.add_section(section)

        Config.__config_parser.set(section, option, str(value))

        Config._write_config()






