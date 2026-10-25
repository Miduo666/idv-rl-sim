use std::{collections::HashMap, env, io::Write};

use pytools::marshal;
mod hash;
mod mmap;
mod npk;
mod nxs;
mod opcode;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // let str = "dm65ui\\res\\system\\note_common\\fame_lock.astc";

    // println!("Hash FNV1a: {:08x}", hash::hash_fnv1a(str));
    // println!("Hash Murmur3: {:08x}", hash::hash_murmur3(str));
    // println!("Hash XXHash: {:08x}", hash::hash_xxhash(str));

    let extracted_path = std::path::Path::new("./extracted");

    let mut files = env::args().skip(1).collect::<Vec<_>>();
    if files.is_empty() {
        eprintln!("Usage: denpk2 <NPK file path>");
        return Ok(());
    }

    let string_list = if files.len() > 1 {
        let last_file = files[files.len() - 1].clone();
        if !last_file.ends_with(".npk") {
            files.pop();

            Some(
                std::fs::read_to_string(last_file)?
                    .lines()
                    .map(String::from)
                    .collect::<Box<[_]>>(),
            )
        } else {
            None
        }
    } else {
        None
    };

    let mut hash_list_map: HashMap<u32, Box<[(u32, u32)]>> = HashMap::new();
    for file in files {
        let data = mmap::new_path(&file)?;
        let npk = npk::NpkIterator::new(data)?;

        let hash_mode = npk.header.hash_mode;
        let hash_list = if let Some(hash_list) = hash_list_map.get(&hash_mode) {
            Some(hash_list)
        } else if let Some(string_list) = &string_list {
            let hash_fn = npk.header.hash_fn();
            let hash_list = generate_hash_list(string_list, hash_fn);

            hash_list_map.insert(hash_mode, hash_list);

            Some(hash_list_map.get(&hash_mode).unwrap())
        } else {
            None
        };

        for (entry, data) in npk {
            println!("{:?}", entry);

            let id = entry.id;

            let unpacked = entry.unpack_data(data)?;
            let (code, header) = if &unpacked[0..8] == nxs::NXS_MAGIC {
                (nxs::unpack(&unpacked)?, marshal::PYC_HEADER)
            } else if unpacked[0..4] == marshal::PYC_HEADER[0..4] {
                (unpacked[16..].to_vec(), unpacked[0..16].try_into()?)
            } else {
                // plain file
                // find for potentially matching hash
                let name = if let Some(hash_list) = hash_list {
                    if let Some((_, index)) = hash_list.iter().find(|(h, _)| *h == id) {
                        string_list
                            .as_ref()
                            .and_then(|list| list.get(*index as usize))
                            .cloned()
                    } else {
                        None
                    }
                } else {
                    None
                };

                let name = name.unwrap_or(format!("blobs/{:08x}", id));

                let output = extracted_path.join(name);
                std::fs::create_dir_all(output.parent().ok_or("No parent")?)?;

                std::fs::write(&output, &unpacked)?;
                continue;
            };

            let py_object = marshal::PyObject::read_root(&code)?;
            let py_object = opcode::map_opcode(py_object)?;

            let marshal::PyObject::Code { filename, .. } = py_object.as_ref() else {
                return Err("Unexpected object type".into());
            };

            // replace windows backslashes with forward slashes
            let filename = filename.as_str().map(|s| s.replace("\\", "/"));
            let output = extracted_path.join(format!("{}.pyc", filename.ok_or("No filename")?));

            std::fs::create_dir_all(output.parent().ok_or("No parent")?)?;

            let file = std::fs::File::create(&output)?;
            let mut writer = std::io::BufWriter::new(file);
            writer.write_all(header)?;
            py_object.write_root(&mut writer, false)?;
        }
    }

    Ok(())
}

fn generate_hash_list(string_list: &[String], hash_fn: hash::HashFn) -> Box<[(u32, u32)]> {
    let mut hash_list: Vec<(u32, u32)> = Vec::with_capacity(string_list.len());
    for (i, string) in string_list.iter().enumerate() {
        let flipped = string.replace('/', "\\");

        let mut str_slice = string.as_str();
        let mut flipped = flipped.as_str();

        loop {
            hash_list.push((hash_fn(str_slice), i as u32));

            if let Some(index) = str_slice.find('/') {
                hash_list.push((hash_fn(flipped), i as u32));

                // slice string by '/'
                str_slice = &str_slice[index + 1..];
                flipped = &flipped[index + 1..];
            } else {
                break;
            }
        }
    }
    hash_list.into_boxed_slice()
}
