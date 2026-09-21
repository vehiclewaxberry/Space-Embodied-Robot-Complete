from spacecraft_model import build
def gen_step():
    return build('released',include_arm=False)[0]
