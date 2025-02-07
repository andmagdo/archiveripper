# ripper.py
# Copyright (c) 2020  James Shiffer
# This file contains the main application logic.

import argparse, api, getpass, logging, os, stitcher, save

if os.path.exists('config.py'):
    from config import config
else:
    config={'email':'','password':''}

def main():
    client = api.ArchiveReaderClient()
    logging.basicConfig(level=logging.INFO)

    # Parse book id and credentials
    parser = argparse.ArgumentParser()
    parser.add_argument('id', nargs='?',
        help='Look for the book\'s identifier (the part of the url immediately after "https://archive.org/details/").')
    parser.add_argument('-u', '--username', help='Your archive.org account\'s email.')
    parser.add_argument('-p', '--password', help='Your archive.org account\'s password')
    parser.add_argument('-a', '--all-pages', action='store_true', help='Download every page of the book')
    parser.add_argument('-s', '--page-start', type=int, help='Download pages starting at page number N and ending at the book\'s last page, or a range if --page-end has been specified')
    parser.add_argument('-e', '--page-end', type=int, help='End of the range of page numbers to download')
    parser.add_argument('-d', '--output-dir', help='Directory you want the pages to be written to. If undefined the directory will be named the book id')
    parser.add_argument('-S', '--scale', default=0, type=int, help='Image resolution of the pages requested, can save bandwidth if the best image quality isn\'t necessary. Higher integers mean smaller resolution, default is 0 (no downscaling)')
    args = parser.parse_args()

    id = args.id
    username = args.username
    password = args.password

    #If any of the credentials isn't specified with cmdline args ask for it interactively
    if not args.id:
        print('Look for the book\'s identifier (the part of the url immediately after "https://archive.org/details/").')
        id = input('Enter it here: ')
        logging.debug('received book ID: %s' % id)
    if not args.username:
        # Check if the email and password of user are stored in config file
        if config['email']:
            username = config['email']
        else:
            username = input('Enter your archive.org email: ')
    if not args.password:
        if config['password']:
            password = config['password']
        else:
            password = getpass.getpass('Enter your archive.org password: ')


    logging.debug('attempting login with user-supplied credentials')
    client.login(username, password)

    logging.debug('attempting to start scheduler')
    client.schedule_loan_book(id)

    if not args.output_dir:
        dir = './' + id
    else:
        dir = os.path.expanduser(args.output_dir)

    logging.debug('creating output dir "%s"' % dir)
    if os.path.isdir(dir):
        response = input('Output folder %s already exists. Continue? ' \
            % dir)
        if not response.lower().startswith('y'):
            return
    else:
        os.mkdir(dir)

    page_count = client.fetch_book_metadata()

    start = 0
    end = page_count

    if not args.all_pages:
        if not args.page_start and not args.page_end:
            print('The book is %d pages long. Which pages do you want?' % page_count)
            while True:
                desired_pages = input('Enter a range (eg. 1-15) or leave blank for all: ')
                if desired_pages:
                    try:
                        [start, end] = desired_pages.split('-')
                        start = int(start) - 1
                        end = int(end)
                    except ValueError:
                        continue
                    break
        else:
            if args.page_start: start = args.page_start - 1
            if args.page_end: end = args.page_end

    logging.debug('planning on fetching pages %d thru %d' % (start, end))

    total = end - start
    failed_pages = []

    for i in range(start, end):
        logging.debug('downloading page %d (index %d)' % (i + 1,
            i))
        try:
            contents = client.download_page(i, args.scale)
        except Exception as e:
            # Retry once if the download fails
            try:
                print('Failed to download page %d, retrying once...' % (i + 1))
                contents = client.download_page(i, args.scale)
            except Exception as e:
                # Retry twice if the download failed again
                print('Failed to download page %d, retrying twice...' % (i + 1))
                try:
                    contents = client.download_page(i, args.scale)
                except Exception as e:
                    print('Failed to download page %d' % (i + 1))
                    failed_pages.append(i + 1)
                continue

        with open('%s/%d.jpg' % (dir, i + 1), 'wb') as file:
            file.write(contents)
        done_count = i + 1 - start
        print('%d%% (%d/%d) done' % (done_count / total * 100, done_count, total))

    if failed_pages:
        print('Failed to download the following pages:')
        print(failed_pages)

    # Stitch the pages together
    stitcher.stitch(dir, id)

    if input('Store login details for later? ').lower().startswith('y'):
        if os.path.exists('config.py'):
            if input('Replace current login details? ').lower().startswith('y'):
                os.remove('config.py')
                save.save_config(username, password)
        else:
            save.save_config(username, password)

    print('done')

if __name__ == '__main__':
    main()
