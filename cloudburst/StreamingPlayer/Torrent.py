import libtorrent as lt
import threading
import time
import appdirs

class Piece():
    def __init__(self, parent):
        self.parent = parent

class Torrent():

    # CONFIG VARS (can edit)
    bufferSize = 10 # in pieces, should be a minimum of paddingSize. Since the peers are lost when the header is available, the buffer needs to be big enough to re-initialize the torrent (around 10 should do) (based on bitrate)
    paddingSize = 3
    headerSize = 1
    footerSize = 1

    enableDebugInfo = True

    # SYSTEM VARS (do not edit)

    torrentHandle = None
    torrentInfo = None
    torrentStatus = None
    torrentSession = None

    isRunning = False

    seekPointPieceNumber = 0 # TODO turn into properties, readonly
    currentPieceNumber = 0
    seekPoint = 0 # from 0 to 1
    totalPieces = -1 # Total amount of pieces in the torrent
    headerAvailable = False


    pieces = {}
    headerPieces = {}
    piecesRequired = 0
    headerPiecesRequired = 0
    piecesPadded = 0

    headerIncreaseSizeCurrent = 0 # starting value, do not edit # TODO figure out what to do with values that need not be edited
    headerIncreaseSizeAmount = 1 # this many pieces are added to the front AND the back of the header buffer
    headerIncreaseOffset = 1 # if this many pieces are missing from the header, headerIncreaseSizeAmount amount are added. Must be higher than headerIncreaseSizeAmount

    downloadLimitEnabled = False

    forwardBufferRequested = False
    forwardBufferAvailable = False
    forwardBufferPieces = {}

    downloadDirectory = '' # cant read from appdirs here, set in init

    def __init__(self, parent):

        # Some sanity checks
        assert self.bufferSize >= self.paddingSize
        # TODO add more

        self.isRunning = True

        self.downloadDirectory = appdirs.dirs.user_cache_dir + '\\Download\\'

        # TODO do not remove downloaded torrent but check it instead
        import shutil
        shutil.rmtree(self.downloadDirectory, ignore_errors=True)

        if lt.version != '0.16.16.0':
            print 'Wrong version of libtorrent detected, please install version 0.16.16.0, you have', lt.version
            import sys
            sys.exit(-1)

        self.torrentSession = lt.session()
        self.torrentSession.listen_on(6881, 6891)

        # Allocation settings (these should be default but make sure they are correct)
        settings = lt.session_settings()
        settings.disk_io_write_mode = lt.io_buffer_mode_t.enable_os_cache
        settings.disk_io_read_mode = lt.io_buffer_mode_t.enable_os_cache

        self.torrentSession.set_settings(settings)

        self.parent = parent

    def Shutdown(self):
        self.isRunning = False

    # Start the torrent and the required threads
    def StartTorrent(self, path, seekpoint = 0):

        self.seekPoint = seekpoint

        if self.torrentHandle is not None:
            print 'Another torrent is already in progress'
            return

        e = lt.bdecode(open(path, 'rb').read())
        self.torrentInfo = lt.torrent_info(e)

        # Print some torrent stats
        if self.enableDebugInfo:
            print 'Torrent piece size:', self.torrentInfo.piece_size(0) / 1024, 'kB'
            print 'Torrent total pieces:', self.torrentInfo.num_pieces()
            print 'Torrent total files:', self.torrentInfo.num_files()

        self.torrentHandle = self.torrentSession.add_torrent({'ti': self.torrentInfo, 'save_path': self.downloadDirectory, 'storage_mode' : lt.storage_mode_t.storage_mode_sparse})

        videoFile = self.FindVideoFile(self.torrentInfo.files())

        # start download thread
        downloadThread = threading.Thread(target=self.DownloadTorrent)
        downloadThread.daemon = True
        downloadThread.start()

        # start alert thread
        alertThread = threading.Thread(target=self.Alert)
        alertThread.daemon = True
        alertThread.start()

        return self.downloadDirectory + videoFile.path


    # Check which pieces already exist in an existing file, if available
    def CheckCache(self):
        for n in iter(self.pieces):
            if self.torrentHandle.have_piece(n):
                self.UpdateHeaderProgress(n, True)  # ignore False state

    # Determine which file in the torrent is the video file. Currently based on size and is checked for extension.
    def FindVideoFile(self, fileList):
        videoFile = lt.file_entry()

        # Currently it is presumed the largest file is the video file. This should be true most of the time.
        for n in range(0, len(fileList)):

            if fileList[n].size > videoFile.size:
                videoFile = fileList[n]
            else: # not the file we want, set to skip -- this is assumed the fileList index corresponds to the torrent priority list
                self.torrentHandle.file_priority(n, 0);


        # Additional check, make sure the file we want (video file) has one of these extensions: .mkv, .avi, .mp4
        splitFileString = str.split(videoFile.path, '.')
        fileExtension = splitFileString[len(splitFileString) - 1]

        if not (fileExtension == 'mkv' or fileExtension == 'avi' or fileExtension == 'mp4'):
            print 'Video file has invalid file extension:', fileExtension
            import sys
            sys.exit(-1)

        return videoFile

    def GetBytesDownloaded(self):
        return self.torrentStatus.total_wanted_done

    def GetBytesWanted(self):
        return self.torrentStatus.total_wanted

    def PrintTorrentDebug(self):

        print 'Avail.\t:',

        # Header
        for n in range(0, self.headerSize):
            if self.torrentHandle.have_piece(n):
                print '1',
            else:
                print '0',

        print '#',

        # Seekpoint
        for n in range(max(self.seekPointPieceNumber - 50, 0), min(self.seekPointPieceNumber + 50, self.totalPieces - 1)):
            if self.torrentHandle.have_piece(n):
                print '1',
            else:
                print '0',

        print '#',

        # Footer
        for n in range(0, self.footerSize):
            if self.torrentHandle.have_piece(self.totalPieces - 1 - n):
                print '1',
            else:
                print '0',

        print ''

        # Priorities

        print 'Prior.\t:',
        # Header
        for n in range(0, self.headerSize):
            if self.torrentHandle.piece_priority(n):
                print '1',
            else:
                print '0',

        print '#',

        # Seekpoint
        for n in range(max(self.seekPointPieceNumber - 50, 0), min(self.seekPointPieceNumber + 50, self.totalPieces - 1)):
            if self.torrentHandle.piece_priority(n):
                print '1',
            else:
                print '0',

        print '#',

        # Footer
        for n in range(0, self.footerSize):
            if self.torrentHandle.piece_priority(self.totalPieces - 1 - n):
                print '1',
            else:
                print '0',

        print ''

    # Enable the download limit # TODO base it on bitrate
    def EnableDownloadLimit(self):
        # Set download speed limit (apparently needs to be set after the torrent adding)
        self.downloadLimitEnabled = True

        downSpeed = 2 * 1024 * 1024
        self.torrentSession.set_download_rate_limit(downSpeed)

        if self.enableDebugInfo:
            print 'Download speed limit set to:', downSpeed / 1024, 'kB/s'

    # Sets the torrent to download the video data starting from the seekpoint
    def IncreaseBuffer(self, missingPieces = None, increasePiecePosition = True):

        pieceDeadlineTime = 5000

        if increasePiecePosition:
            self.currentPieceNumber += self.bufferSize

        pieceList = [0] * self.torrentInfo.num_pieces()

        self.pieces.clear()

        if missingPieces != None:

            for n in range(0, len(missingPieces)):

                higherPriority = 2
                pieceDeadlineTime = 2000

                pieceList[missingPieces[n]] = higherPriority # higher priority

                self.pieces[missingPieces[n]] = False
                self.torrentHandle.set_piece_deadline(missingPieces[n], pieceDeadlineTime, 1)

        for n in range(0, self.bufferSize):
            piece = self.currentPieceNumber + n

            self.pieces[piece] = False
            pieceList[piece] = 1 # priority
            self.torrentHandle.set_piece_deadline(piece, pieceDeadlineTime, 1) # set deadline and enable alert

        self.piecesRequired = len(self.pieces)

        self.torrentHandle.prioritize_pieces(pieceList)

        return self.pieces.copy()

    # Increase the header at the front and the back of the header, in order to find the point from where mkv can play.
    # The missingPieces argument contains pieces that were not yet in and will be priotized.
    def IncreaseHeader(self, missingPieces = None):

        pieceDeadlineTime = 5000

        self.headerIncreaseSizeCurrent += 1

        pieceList = [0] * self.torrentInfo.num_pieces()

        self.headerPieces.clear()

        if missingPieces != None:

            for n in range(0, len(missingPieces)):

                higherPriority = 2 # The priority for missing pieces

                # Make sure header pieces get even higher priority, since the video must wait for these before starting
                if missingPieces[n] > self.totalPieces - self.footerSize - 1 or missingPieces[n] < self.headerSize:
                    higherPriority = 3 # The priority for missing header pieces
                    pieceDeadlineTime = 2000

                pieceList[missingPieces[n]] = higherPriority # higher priority

                self.headerPieces[missingPieces[n]] = False
                self.torrentHandle.set_piece_deadline(missingPieces[n], pieceDeadlineTime, 1)

        # Increase the header by adding x to the back and x to the front of the header.
        pieceFront = self.currentPieceNumber + self.headerIncreaseSizeCurrent
        pieceBack = self.currentPieceNumber - self.headerIncreaseSizeCurrent

        if pieceFront < self.totalPieces - self.footerSize:
            self.headerPieces[pieceFront] = False # to keep track of availability
            pieceList[pieceFront] = 1 # priority
            self.torrentHandle.set_piece_deadline(pieceFront, pieceDeadlineTime, 1) # set deadline and enable alert

        if pieceBack >= self.headerSize:
            self.headerPieces[pieceBack] = False # to keep track of availability
            pieceList[pieceBack] = 1 # priority
            self.torrentHandle.set_piece_deadline(pieceBack, pieceDeadlineTime, 1) # set deadline and enable alert

        self.headerPiecesRequired = len(self.headerPieces)

        self.torrentHandle.prioritize_pieces(pieceList)

    # Seekpoint is the float from 0 to 1 where the video should play from
    def SetSeekPoint(self, seekpoint):

        if self.enableDebugInfo:
            print 'Seekpoint set to:', seekpoint

        self.seekPoint = seekpoint

        # Seekpoint position
        self.currentPieceNumber = int(float(self.totalPieces) / 1 * self.seekPoint)
        self.seekPointPieceNumber = self.currentPieceNumber

        self.headerAvailable = False

    # When header is in, call this function. Start to play movie and enable custom sequential download
    def SetHeaderAvailable(self):
        self.parent.HeaderAvailable(True)
        self.headerAvailable = True
        print 'Header available'

        if self.enableDebugInfo:
            self.PrintTorrentDebug()

    def IsHeaderAvailable(self):
        available = True

        for n in iter(self.headerPieces):

            for n in range(0, self.headerSize):
                if not self.headerPieces[n]:
                    available = False

            for n in range(self.totalPieces - self.footerSize, self.totalPieces):
                if not self.headerPieces[n]:
                    available = False

            if n == self.seekPointPieceNumber:
                if not self.headerPieces[self.seekPointPieceNumber]:
                    available = False

        return available

    def SetForwardBufferAvailable(self):
        self.forwardBufferAvailable = True
        self.parent.forwardBufferAvailable = True

        if not self.downloadLimitEnabled:
            self.EnableDownloadLimit()

        print 'Forward buffer available'

    def IsForwardBufferAvailable(self, pieceNumber):

        if pieceNumber in self.forwardBufferPieces:
            self.forwardBufferPieces[pieceNumber] = True

        available = True
        for n in iter(self.forwardBufferPieces):
            if not self.forwardBufferPieces[n]:
                available = False

        return available


    def UpdatePieceList(self, pieceNumber): # TODO incorporate timer that sets deadlines and increases buffer
        if self.enableDebugInfo:
            print 'Updated piece', pieceNumber


        if not self.forwardBufferAvailable and self.forwardBufferRequested:
            if self.IsForwardBufferAvailable(pieceNumber):
                self.SetForwardBufferAvailable()

        if pieceNumber in self.pieces:
            if not self.pieces[pieceNumber]:
                self.pieces[pieceNumber] = True
            # else: # piece was already set to true, the alert was a duplicate, ignore it
            #     return

        if pieceNumber in self.headerPieces:
            if not self.headerPieces[pieceNumber]:
                self.headerPieces[pieceNumber] = True
            # else: # piece was already set to true, the alert was a duplicate, ignore it
            #     return

        pieceAvailableCount = 0
        for n in iter(self.pieces):
            if self.pieces[n]:
                pieceAvailableCount += 1

        headerPieceAvailableCount = 0
        for n in iter(self.headerPieces):
            if self.headerPieces[n]:
                headerPieceAvailableCount += 1

        if not self.headerAvailable:
            if self.IsHeaderAvailable():
                self.SetHeaderAvailable()


        if self.parent.isPlaying:
            assert self.headerAvailable

        # if header available, the mkv may not yet play. increase the buffer on both ends and keep trying to play.
        if not self.parent.isPlaying:

            if headerPieceAvailableCount >= (self.headerPiecesRequired - self.headerIncreaseOffset):
                missingPieces = []
                for n in iter(self.headerPieces):
                    if not self.headerPieces[n]:
                        missingPieces.append(n)

                self.IncreaseHeader(missingPieces)

        else: # if header + extra pieces large enough (so actually playing), start sequential download

            if pieceAvailableCount >= (self.piecesRequired - self.paddingSize): # x pieces left

                missingPieces = []
                for n in iter(self.pieces):
                    if not self.pieces[n]:
                        missingPieces.append(n)

                # add missing piece as argument so they can be prioritized
                if not self.forwardBufferRequested:
                    self.currentPieceNumber += self.headerIncreaseSizeCurrent # add the additional pieces amount
                    self.forwardBufferPieces = self.IncreaseBuffer(missingPieces=missingPieces, increasePiecePosition=False)
                    self.forwardBufferRequested = True
                else:
                    self.IncreaseBuffer(missingPieces=missingPieces)



    def InitializePieces(self):

        self.totalPieces = self.torrentInfo.num_pieces()

        # Check cache once, in case the file already existed
        self.CheckCache() # TODO test this works

        # Seekpoint position
        self.currentPieceNumber = int(float(self.totalPieces) / 1 * self.seekPoint)
        self.seekPointPieceNumber = self.currentPieceNumber

        # Header pieces
        for n in range(0, self.headerSize):
            self.headerPieces[n] = False                # start of the file

        # Footer size (MKV Cueing data)
        if self.seekPointPieceNumber > 0: # footer is only required for seeking # TODO make sure the footer does get downloaded when seeking after playing from 0
            for n in range(0, self.footerSize):
                self.headerPieces[self.totalPieces - 1 - n] = False  # end of the file (MKV needs this) # TODO not needed for avi?

        if self.enableDebugInfo:
            print 'Seekpoint piece:', self.seekPointPieceNumber

        if self.currentPieceNumber < 0:
            self.currentPieceNumber = 0

        # Set the entire priority list to skip
        pieceList = [0] * self.totalPieces

        # Save pieces so we can check them later
        self.headerPieces[self.currentPieceNumber] = False

        # Save how many we set for later
        self.headerPiecesRequired = len(self.headerPieces)

        # Set headers to high priority
        for n in iter(self.headerPieces):
            pieceList[n] = 1
            self.torrentHandle.set_piece_deadline(n, 5000, 1)   # 1 is alert_when_available

        # Set the list to the torrent handle
        self.torrentHandle.prioritize_pieces(pieceList)

    def Alert(self):    # Thread. Checks torrent alert messages (like piece ready) and processes them
        pieceTextToFind = 'piece successful' # Libtorrent always reports this when a piece is succesful, with an int attached

        while not self.torrentHandle.is_seed() and self.isRunning:
            if self.torrentSession.wait_for_alert(10) is not None: # None means no alert, timeout
                alert = str(self.torrentSession.pop_alert())

                if pieceTextToFind in alert: # So we extract the int from the text
                    alertSubString = alert.find(pieceTextToFind)
                    pieceNumber = int(alert[alertSubString + len(pieceTextToFind):])

                    # And pass it on to the method that checks pieces
                    self.UpdatePieceList(pieceNumber) # TODO fix alert spam (has to do with setting deadline on pieces that are already in)

                # print alert # Uncomment this to see all alerts

    def DownloadTorrent(self): # thread

        self.InitializePieces()

        while not self.torrentHandle.is_seed() and self.isRunning: # while not finished
            self.torrentStatus = self.torrentHandle.status()

            if self.torrentStatus.progress != 1:
                state_str = ['queued', 'checking', 'downloading metadata',
                        'downloading', 'finished', 'seeding', 'allocating', 'checking fastresume']
                print '\rdown: %.1f kB/s, peers: %d, status: %s' % \
                    (self.torrentStatus.download_rate / 1000,
                    self.torrentStatus.num_peers, state_str[self.torrentStatus.state])

            if self.enableDebugInfo:
                self.PrintTorrentDebug()


            time.sleep(3)

        print self.torrentHandle.name(), 'completed'