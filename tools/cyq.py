import marshal, sys, dis, os
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'std_pyc')
for rel in sys.argv[1:]:
    co = marshal.loads(open(os.path.join(ROOT, rel), 'rb').read()[16:])
    ins = list(dis.get_instructions(co))
    out = [[y.argval for y in ins[i+1:i+3]] for i, x in enumerate(ins) if x.opname == 'LOAD_NAME' and x.argval == 'import_cy_module_cls']
    print(rel, out)
