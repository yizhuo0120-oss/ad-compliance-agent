Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $s.SelectVoice('Microsoft Huihui Desktop')
} catch {
    try { $s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Female) } catch {}
}
$s.SetOutputToWaveFile($args[0])
$s.Speak($args[1])
$s.Dispose()
