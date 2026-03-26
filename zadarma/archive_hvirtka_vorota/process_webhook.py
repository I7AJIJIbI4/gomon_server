#!/usr/bin/env python3
import sys
import json
import logging

logging.basicConfig(filename='/home/gomoncli/zadarma/webhook_processor.log', level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    if len(sys.argv) < 2:
        print("ERROR")
        return 1
    
    try:
        data = json.loads(sys.argv[1])
        duration = int(data.get('duration', 0))
        disposition = data.get('disposition', '').upper()
        
        if duration > 0 or disposition == 'ANSWERED':
            logger.info('Успішний дзвінок: duration={}, disposition={}'.format(duration, disposition))
            print("SUCCESS")
            return 0
        else:
            logger.info('Неуспішний дзвінок: duration={}, disposition={}'.format(duration, disposition))
            print("ERROR") 
            return 1
    except Exception as e:
        logger.error('Помилка: {}'.format(e))
        print("ERROR")
        return 1

if __name__ == "__main__":
    exit(main())
