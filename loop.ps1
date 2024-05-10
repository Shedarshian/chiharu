while ($true) {
    & "C:\Program Files\proxychains_0.6.8_win32_x64\proxychain.exe" python ./bot-nb2.py
    echo "restarting in 5 seconds"
    Start-Sleep -Seconds 5
}