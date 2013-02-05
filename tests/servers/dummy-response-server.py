import argparse
from werkzeug.wrappers import Request, Response

global response_mimetype
global response_content

@Request.application
def application(request):
    return Response(response_content, mimetype=response_mimetype)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Starts an http server that blindly responds whatever it was initialized with.")
    parser.add_argument("port", help="port number")
    parser.add_argument("response_file", help="file that contains response content")
    parser.add_argument("response_mimetype", help="mimetype to use for response")
    args = parser.parse_args()

    #read file into buffer
    print 'Response Content: ' + args.response_file
    global response_content
    f = open(args.response_file, 'rb')
    response_content = f.read()
    f.close()

    #set mimetype
    print 'Response Mimetype: ' + args.response_mimetype
    global response_mimetype
    response_mimetype = args.response_mimetype

    from werkzeug.serving import run_simple
    run_simple('localhost', int(args.port), application)