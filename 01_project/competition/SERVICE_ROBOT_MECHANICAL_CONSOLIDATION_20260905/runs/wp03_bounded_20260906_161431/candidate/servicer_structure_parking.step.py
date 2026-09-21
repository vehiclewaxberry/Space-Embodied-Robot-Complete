from spacecraft_model import build
def gen_step():
    return build('parking',include_arm=False)[0]
