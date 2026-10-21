; desktop/src-tauri/installer/nsis-hooks.nsh
; Custom branding text shown at the bottom border of the Windows NSIS wizard
BrandingText "FLAC Meta Injector Studio • Bit-Perfect Audio Tagging"

!macro NSIS_HOOK_PREINSTALL
  ; Ensure any running background bridge process is closed before overwriting binaries
  nsExec::ExecToLog 'taskkill /F /IM flac-bridge.exe /T'
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  nsExec::ExecToLog 'taskkill /F /IM flac-bridge.exe /T'
!macroend