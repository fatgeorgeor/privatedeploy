pwd=$(pwd)
project=$(basename $pwd)
git archive --format=tar.gz -o $project.tar.gz --prefix=$project/ HEAD
