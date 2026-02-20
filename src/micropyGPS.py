"""
# MicropyGPS - a GPS NMEA sentence parser for Micropython/Python 3.X
# Copyright (c) 2017 Michael Calvin McCoy (calvin.mccoy@protonmail.com)
# The MIT License (MIT) - see LICENSE file
#
# Stripped down for GPS clock: removed unused parsers (VTG, GLL),
# helpers, logging, and features not needed by the application.
# Optimized: update() accepts raw bytes, uses bytearray buffer.
"""


class MicropyGPS(object):
    """GPS NMEA Sentence Parser. Creates object that stores all relevant GPS data and statistics.
    Parses sentences one character at a time using update(). """

    # Max Number of Characters a valid sentence can be (based on GGA sentence)
    SENTENCE_LIMIT = 90
    __HEMISPHERES = ('N', 'S', 'E', 'W')

    __slots__ = ('sentence_active', 'process_crc', 'gps_segments', 'crc_xor',
                 'char_count', 'crc_fails', 'clean_sentences', 'parsed_sentences',
                 'timestamp', 'date', '_latitude', '_longitude',
                 'satellites_in_view', 'satellites_in_use', 'valid', 'fix_type',
                 '_buf', '_buf_len', '_crc_buf', '_crc_len')

    def __init__(self):
        #####################
        # Object Status Flags
        self.sentence_active = False
        self.process_crc = False
        self.gps_segments = []
        self.crc_xor = 0
        self.char_count = 0

        #####################
        # Sentence Statistics
        self.crc_fails = 0
        self.clean_sentences = 0
        self.parsed_sentences = 0

        #####################
        # Data From Sentences
        # Time
        self.timestamp = [0, 0, 0.0]
        self.date = [0, 0, 0]

        # Position
        self._latitude = [0, 0.0, 'N']
        self._longitude = [0, 0.0, 'W']

        # GPS Info
        self.satellites_in_view = 0
        self.satellites_in_use = 0
        self.valid = False
        self.fix_type = 1

        #####################
        # Bytearray sentence buffer
        self._buf = bytearray(self.SENTENCE_LIMIT)
        self._buf_len = 0
        self._crc_buf = bytearray(2)
        self._crc_len = 0

    ########################################
    # Sentence Parsers
    ########################################
    def gprmc(self):
        """Parse Recommended Minimum Specific GPS/Transit data (RMC) Sentence.
        Updates UTC timestamp, latitude, longitude, Date, and fix status"""

        # UTC Timestamp
        try:
            utc_string = self.gps_segments[1]

            if utc_string:
                hours = int(utc_string[0:2]) % 24
                minutes = int(utc_string[2:4])
                seconds = float(utc_string[4:])
                self.timestamp = [hours, minutes, seconds]
            else:
                self.timestamp = [0, 0, 0.0]

        except ValueError:
            return False

        # Date stamp
        try:
            date_string = self.gps_segments[9]

            if date_string:
                day = int(date_string[0:2])
                month = int(date_string[2:4])
                year = int(date_string[4:6])
                self.date = (day, month, year)
            else:
                self.date = (0, 0, 0)

        except ValueError:
            return False

        # Check Receiver Data Valid Flag
        if self.gps_segments[2] == 'A':

            # Longitude / Latitude
            try:
                # Latitude
                l_string = self.gps_segments[3]
                lat_degs = int(l_string[0:2])
                lat_mins = float(l_string[2:])
                lat_hemi = self.gps_segments[4]

                # Longitude
                l_string = self.gps_segments[5]
                lon_degs = int(l_string[0:3])
                lon_mins = float(l_string[3:])
                lon_hemi = self.gps_segments[6]
            except ValueError:
                return False

            if lat_hemi not in self.__HEMISPHERES:
                return False

            if lon_hemi not in self.__HEMISPHERES:
                return False

            # Update Object Data
            self._latitude = [lat_degs, lat_mins, lat_hemi]
            self._longitude = [lon_degs, lon_mins, lon_hemi]
            self.valid = True

        else:
            self._latitude = [0, 0.0, 'N']
            self._longitude = [0, 0.0, 'W']
            self.valid = False

        return True

    def gpgga(self):
        """Parse Global Positioning System Fix Data (GGA) Sentence. Updates UTC timestamp, latitude, longitude,
        fix status, and satellites in use"""

        try:
            utc_string = self.gps_segments[1]

            if utc_string:
                hours = int(utc_string[0:2]) % 24
                minutes = int(utc_string[2:4])
                seconds = float(utc_string[4:])
            else:
                hours = 0
                minutes = 0
                seconds = 0.0

            satellites_in_use = int(self.gps_segments[7])
            fix_stat = int(self.gps_segments[6])

        except (ValueError, IndexError):
            return False

        if fix_stat:

            try:
                l_string = self.gps_segments[2]
                lat_degs = int(l_string[0:2])
                lat_mins = float(l_string[2:])
                lat_hemi = self.gps_segments[3]

                l_string = self.gps_segments[4]
                lon_degs = int(l_string[0:3])
                lon_mins = float(l_string[3:])
                lon_hemi = self.gps_segments[5]
            except ValueError:
                return False

            if lat_hemi not in self.__HEMISPHERES:
                return False

            if lon_hemi not in self.__HEMISPHERES:
                return False

            self._latitude = [lat_degs, lat_mins, lat_hemi]
            self._longitude = [lon_degs, lon_mins, lon_hemi]

        self.timestamp = [hours, minutes, seconds]
        self.satellites_in_use = satellites_in_use

        return True

    def gpgsa(self):
        """Parse GNSS DOP and Active Satellites (GSA) sentence. Updates fix type."""
        try:
            self.fix_type = int(self.gps_segments[2])
        except ValueError:
            return False
        return True

    def gpgsv(self):
        """Parse Satellites in View (GSV) sentence. Updates satellites in view count."""
        try:
            self.satellites_in_view = int(self.gps_segments[3])
        except (ValueError, IndexError):
            return False
        return True

    ##########################################
    # Data Stream Handler Functions
    ##########################################

    def new_sentence(self):
        """Adjust Object Flags in Preparation for a New Sentence"""
        self._buf_len = 0
        self._crc_len = 0
        self.crc_xor = 0
        self.sentence_active = True
        self.process_crc = True
        self.char_count = 0

    def update(self, new_byte):
        """Process a new input byte and updates GPS object if necessary based on special characters ('$', ',', '*')
        Function builds a bytearray buffer that is decoded and split into segments on valid CRC,
        then parsed by the appropriate sentence function. Returns sentence type on successful parse, None otherwise"""

        valid_sentence = False

        if 10 <= new_byte <= 126:
            self.char_count += 1

            if new_byte == 36:  # '$'
                self.new_sentence()
                return None

            elif self.sentence_active:

                if new_byte == 42:  # '*'
                    self.process_crc = False
                    return None

                if self.process_crc:
                    # Data byte (including commas) — accumulate and XOR
                    self._buf[self._buf_len] = new_byte
                    self._buf_len += 1
                    self.crc_xor ^= new_byte
                else:
                    # CRC hex digit
                    self._crc_buf[self._crc_len] = new_byte
                    self._crc_len += 1
                    if self._crc_len == 2:
                        try:
                            final_crc = int(self._crc_buf.decode(), 16)
                            if self.crc_xor == final_crc:
                                valid_sentence = True
                            else:
                                self.crc_fails += 1
                        except ValueError:
                            pass

                if valid_sentence:
                    self.clean_sentences += 1
                    self.sentence_active = False

                    # Decode buffer and split into segments
                    self.gps_segments = self._buf[:self._buf_len].decode().split(',')

                    if self.gps_segments[0] in self.supported_sentences:

                        if self.supported_sentences[self.gps_segments[0]](self):

                            self.parsed_sentences += 1
                            return self.gps_segments[0]

                if self.char_count > self.SENTENCE_LIMIT:
                    self.sentence_active = False

        return None

    # All the currently supported NMEA sentences
    supported_sentences = {'GPRMC': gprmc, 'GLRMC': gprmc,
                           'GPGGA': gpgga, 'GLGGA': gpgga,
                           'GPGSA': gpgsa, 'GLGSA': gpgsa,
                           'GPGSV': gpgsv, 'GLGSV': gpgsv,
                           'GNGGA': gpgga, 'GNRMC': gprmc,
                           'GNGSA': gpgsa,
                          }
