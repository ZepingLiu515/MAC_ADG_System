import os, json, importlib
print("Python:", os.sys.executable)
pkgs = ["paddleocr","paddle","paddlepaddle","paddlex"]
for p in pkgs:
    try:
        m = importlib.import_module(p)
        v = getattr(m, "__version__", "unknown")
        print(p, v)
    except Exception as e:
        print(p, "ERROR:", e)

base = os.path.join(os.path.expanduser("~"), ".paddlex", "official_models")
print("paddlex models dir:", base, "exists:", os.path.exists(base))
if os.path.exists(base):
    for root, dirs, files in os.walk(base):
        for f in files[:50]:
            fp = os.path.join(root, f)
            try:
                size = os.path.getsize(fp)
            except Exception as e:
                size = f"ERR:{e}"
            print(root.replace(os.path.expanduser("~"), "~"), "/", f, size)
            if f.lower().endswith(".json"):
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                        print("  json head:", fh.read(200).replace("\n"," "))
                except Exception as e:
                    print("  cannot read json:", e)