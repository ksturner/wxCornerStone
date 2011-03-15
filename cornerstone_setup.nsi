!define py2exeOutputDirectory 'dist\cornerstone'
!define exe 'CornerStone.exe'

; Comment out the "SetCompress Off" line and uncomment
; the next line to enable compression. Startup times
; will be a little slower but the executable will be
; quite a bit smaller
;SetCompress Off
SetCompressor lzma

Name 'CornerStone'
OutFile ${exe}
SilentInstall silent
;Icon 'icon.ico'

Section
    InitPluginsDir
    SetOutPath '$PLUGINSDIR'
    File '${py2exeOutputDirectory}\*.*'

    GetTempFileName $0
    DetailPrint $0
    Delete $0
    StrCpy $0 '$0.bat'
    FileOpen $1 $0 'w'
    FileWrite $1 '@echo off$\r$\n'
    StrCpy $2 $TEMP 2
    FileWrite $1 '$2$\r$\n'
    FileWrite $1 'cd $PLUGINSDIR$\r$\n'
    FileWrite $1 '${exe}$\r$\n'
    FileClose $1
    nsExec::Exec $0
    Delete $0
SectionEnd
