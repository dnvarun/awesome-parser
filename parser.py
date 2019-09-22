import sys, os
import pandas as pd
import re
import requests

'''
What does it do?
Returns a list of projects with #stars #forks and other attributes in 
dataframes for each topic in files like 
https://github.com/avelino/awesome-go/blob/master/README.md

How does it do?
- First parses the contents section to get the list of topics.
- For each header check if it represents a subtopic and parses the section to 
get the list of projects. For each link do an api request to get the required
attributes to get rich info
'''

def is_header(line):
    return line.startswith('#')

def is_contents_header(line):
    return is_header(line) and line.endswith('Contents')

def get_topic_name_from_header(line):
    topic_name = line[line.rfind('#')+1:]
    return topic_name.strip().lower()

def get_topic_name_from_list_item(line):
    m = re.fullmatch('- \[(.*)\]\(#.*\)', line)
    if m is None:
        return ''
    else:
        return m.group(1).lower()

def get_repo_info_from_url(project_url):
    m = re.match('https://github.com/([-.\w]+)/([-.\w]+)', project_url)
    if m is None:
        return '', ''
    else:
        return m.group(1), m.group(2)


def get_project_info(line):
    m = re.match('\* \[([-./\w]*)\]\((((http|https)\:\/\/)?[a-zA-Z0-9\.\/\?\:@\-_=#]+\.([a-zA-Z]){2,6}([a-zA-Z0-9\.\&\/\?\:@\-_=#])*)\)', line)
    if m is None:
        return []
    else:
        project_name = m.group(1)
        project_url = m.group(2)
        print('[Processing]', project_url)
        repo_owner, repo_name = get_repo_info_from_url(project_url)
        print('[Repo Info]', repo_owner, repo_name)
        num_stars = -1
        if repo_owner != '' and repo_name != '':
            # get other repo info using github api

            headers = {'Authorization': 'bearer '+os.environ['GITHUB_AWESOME_PARSER_TOKEN']}
            query_str = 'query { repository(owner: "%s", name: "%s") { stargazers { totalCount } } rateLimit {limit cost remaining resetAt}}' % (repo_owner, repo_name)
            payload = {'query' : query_str}
            resp = requests.post('https://api.github.com/graphql', json = payload, headers = headers)
            if resp.status_code == 200:
                git_info = resp.json()['data']['repository']
                if git_info is None:
                    print('[FATAL]', 'Unknown repo: ', project_url)
                    num_stars = 0
                else:
                    num_stars = git_info['stargazers']['totalCount']

        return [project_name, project_url, num_stars]
    

def parse(filename):
    topics = dict()
    cur_topic_name = ''

    contents_parse_state = 0 # 0 not found, 1 - parsing, 2 - done
    with open(filename) as f:
        for line in f:
            line = line.strip()
            # print('[Parsing] ', line)
            # Contents section not yet found
            if contents_parse_state == 0:
                if is_contents_header(line):
                    contents_parse_state = 1
            # Contents section is being parsed
            elif contents_parse_state == 1:
                # check if we reached end of contents
                if is_header(line):
                    contents_parse_state = 2
                    cur_topic_name = get_topic_name_from_header(line)
                else:
                    topic_name = get_topic_name_from_list_item(line)
                    # print('[Inserting topic]', topic_name)
                    topics[topic_name] = []
            # Contents section parsing done. now look for projects
            elif contents_parse_state == 2:
                if is_header(line):
                    cur_topic_name = get_topic_name_from_header(line)
                    if cur_topic_name not in topics:
                        topics[cur_topic_name] = []
                else:
                    project_info = get_project_info(line)
                    if len(project_info) > 0:
                        # print('[Cur topic]', cur_topic_name)
                        topics[cur_topic_name].append(project_info)
            # print('[state] ', contents_parse_state)
    topic_dfs = dict()
    for topic_name, projects in topics.items():
        df = pd.DataFrame(projects, columns = ['Name', 'URL', 'Stars'])
        topic_dfs[topic_name] = df
    return topic_dfs

if __name__ == '__main__':
    if len(sys.argv) < 3 :
        print('Usage: ', sys.argv[0], ' <input md file> <output csv file>')
        sys.exit(1)
    dfs_by_topic = parse(sys.argv[1])
    all_dfs = []
    for topic in list(dfs_by_topic.keys()):
        df = dfs_by_topic[topic]
        df['Category'] = topic
        all_dfs.append(df)
    df_all = pd.concat(all_dfs)
    df_all.to_csv(sys.argv[2], index = None)
