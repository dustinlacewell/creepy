
from distutils.core import setup

PROJECT = 'creepy'
setup(
    name=PROJECT,
    packages=[PROJECT] + ['twisted.plugins'],
    version='0.0.1',

    requires=(
        'twisted==12.1.0', 
        'txrestapi', 
        'shortuuid', 
        'txrdq'
    ),

    # url='',
    # author='',
    # author_email='',
)

# Make Twisted regenerate the dropin.cache, if possible.  This is necessary
# because in a site-wide install, dropin.cache cannot be rewritten by
# normal users.
try:
    from twisted.plugin import IPlugin, getPlugins
except ImportError:
    pass
else:
    list(getPlugins(IPlugin))

