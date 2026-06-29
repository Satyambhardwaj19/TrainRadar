from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return '<h1>Welcome to TrainRadar</h1><p>Live UK train tracking coming soon.</p>'

@app.route('/about')
def about():
    return '<h1>About TrainRadar</h1><p>This app was built by Satyam Bhardwaj as part of an MSc dissertation at the University of Liverpool.</p>'

if __name__ == '__main__':
    app.run(debug=True)