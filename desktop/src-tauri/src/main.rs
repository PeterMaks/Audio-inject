// Prevents additional console window on Windows in both dev and release modes
#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

fn main() {
    flac_meta_injector_desktop_lib::run();
}
