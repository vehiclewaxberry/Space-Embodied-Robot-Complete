from spacecraft_model import build
def gen_step():
    return build('service',include_arm=False)[0]
