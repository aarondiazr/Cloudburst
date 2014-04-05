

class VlcInterface:
    def __init__(self, browser):
        self.browser = browser
        self.frame = browser.GetMainFrame()

    def loadVideo(self, jsCallback):
        # jsCallback.Call('file:///D:\\temp\\Frozen.2013.FRENCH.720p.BluRay.x264-ROUGH\\Frozen.2013.FRENCH.720p.BluRay.x264-ROUGH.mkv')
        # jsCallback.Call(self.callback)
        pass

    def openFile(self, path):
        fullPath = 'file:///' + path
        self.frame.CallFunction('openFile', fullPath)

        # self.frame.ExecuteJavascript('var vlc = document.getElementById(\"vlc\");' # TODO cant get this to work
        #                              'vlc.playlist.items.clear();'
        #                              'var options = new Array(\":aspect-ratio=4:3\", \"--rtsp-tcp\");'
        #                              'fileID = vlc.playlist.add(\"' + fullPath + '\", \"fancy name\", options);')

    def play(self): # TODO check which of these functions is actually used by the back end
        self.frame.ExecuteJavascript('vlc.playlist.playItem(fileID);')

    def pause(self):
        self.frame.ExecuteJavascript('vlc.playlist.pause();')

    def playPause(self):
        self.frame.ExecuteJavascript('vlc.playlist.togglePause();')

    def stop(self):
        self.frame.ExecuteJavascript('vlc.playlist.stop();')

    def setPosition(self, position):
        print str(position)
        self.frame.ExecuteJavascript('vlc.input.position = ' + str(position) + ';')

    def getPosition(self):
        pass

    def setTime(self, ms):
        self.frame.ExecuteJavascript('vlc.input.time = ' + str(ms) + ';')

    def test(self):
        print "Test method"
        # print self.frame.ExecuteJavascript('return vlc.input.position')
        pass