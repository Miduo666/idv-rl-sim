use twox_hash::XxHash32;

pub type HashFn = fn(&str) -> u32;

pub fn hash_fnv1a(str: &str) -> u32 {
    let mut hash = 0x811c9dc5u32;
    for byte in str.bytes() {
        hash ^= byte as u32;
        hash = hash.wrapping_mul(0x01000193);
    }
    hash
}

pub fn hash_murmur3(str: &str) -> u32 {
    mur3::murmurhash3_x86_32(str.as_bytes(), 0x9747B28C)
}

pub fn hash_xxhash(str: &str) -> u32 {
    XxHash32::oneshot(0, str.as_bytes())
}
