from spacecraft_model import build
def gen_step():
    return build('parking',view='cutaway',include_arm=False)[0]
