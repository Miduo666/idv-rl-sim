# denpk2

Unpacks the NXPK files from games with NeoX 2 Engine.

## Information

The reverse engineering is done on the limited beta version of the Identity V game.

> https://h55.gdl.netease.com/dwrg_nx2_gongyan_release_20240509.apk  
> backup: https://drive.google.com/drive/folders/1JpQCiteHn-nknXqlSE1wzAwMilZ2xSf3

## Engine changes

The engine has updated it's embedded python from 2.7.3 to 3.11.6.  
And changes the rotor encryption in `redirect.nxs` to a `RSA` and `XOR` based custom encryption,
the `redirect.nxs` is removed, and the script loading seems to be handled by the native code.

The `marshal` format of the Python language stays untouched,
so the `marshal` module can be used to load the unpacked code objects.
The opcodes has been shuffled as well, so the `dis` module can't be used to disassemble the code objects.

## Usage

Extract the python scripts and generate file list

```bash
cargo run ./dat/script.npk

# make sure to use the same python version as the one used in the game
# to be able to load the code objects
python3.11 ./scripts/generate_filelist.py
```

Or else you can hook the hash function in the game and dump the file list.

Then you can pass the file list to the tool to unpack assets

```bash
cargo run ./dat/wwise.mini.npk ./dat/ui.mini.npk ./dat/strings.list
```
