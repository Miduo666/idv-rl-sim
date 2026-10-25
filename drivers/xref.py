# -*- coding: utf-8 -*-
import sys, struct
SO=sys.argv[1]; targets=set(int(x,16) for x in sys.argv[2:])
import os
TEXT_OFF=int(os.environ.get('TEXT_OFF','0x3b09000'),16); TEXT_SIZE=int(os.environ.get('TEXT_SIZE','0x5f0983c'),16)
with open(SO,"rb") as f:
    f.seek(TEXT_OFF); data=f.read(TEXT_SIZE)
n=len(data)//4
words=struct.unpack("<%dI"%n, data[:n*4])
def sx(v,b):
    return v-(1<<b) if v&(1<<(b-1)) else v
adrp_page=[None]*32   # last ADRP target page per reg
hits=[]
for i in range(n):
    w=words[i]; pc=TEXT_OFF+i*4
    if (w & 0x9F000000)==0x90000000:  # ADRP
        rd=w&0x1F; immlo=(w>>29)&3; immhi=(w>>5)&0x7FFFF
        imm=sx((immhi<<2)|immlo,21)<<12
        adrp_page[rd]=(pc & ~0xFFF)+imm
    elif ((w>>23)&0x1FF)==0x122:  # ADD imm 64-bit
        rn=(w>>5)&0x1F; rd=w&0x1F; sh=(w>>22)&1; imm12=(w>>10)&0xFFF
        base=adrp_page[rn]
        if base is not None:
            tgt=base+(imm12<<(12 if sh else 0))
            if tgt in targets:
                hits.append((pc,tgt,rd))
        # ADD 不清 adrp_page[rd] 以兼容后续 ldr，但若 rd!=rn 其页失效
        if rd!=rn: adrp_page[rd]=None
    # 写其它寄存器的指令粗略不清, 命中足够
for pc,tgt,rd in hits:
    print("xref 0x%08X -> 0x%08X (x%d)"%(pc,tgt,rd))
print("total %d xref sites"%len(hits))
