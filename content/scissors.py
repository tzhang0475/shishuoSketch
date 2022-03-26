'''
scissors to cut original novel into pieces

'''
import sys


# function to transfer chinese digits to aribic digits
# by dodopy https://segmentfault.com/a/1190000013048884
# with a bit modification 
def _trans(s):
    digit = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
    num = 0
    if s:
        idx_q, idx_b, idx_s = s.find('千'), s.find('百'), s.find('十')
        if idx_q != -1:
            num += digit[s[idx_q - 1:idx_q]] * 1000
        if idx_b != -1:
            num += digit[s[idx_b - 1:idx_b]] * 100
        if idx_s != -1:
            # 十前忽略一的处理
            num += digit.get(s[idx_s - 1:idx_s], 1) * 10
        if s[-1] in digit:
            num += digit[s[-1]]
#    if int(num)<10:
#        num = str(0)+str(num)
    return num

# fetch the category of the novel
def cate_fetch(infile):
    category = {}
    with open(infile,'r') as f:
        for line in f:
            if line.strip() and len(line)>=3:
                if line[2]=='第':
                    line = line.rstrip()
                    if line[-1]=='上' or line[-1]=='下':
                        line = line.rstrip(line[-1])
                    cn_num = str(line[3:])
                    num = _trans(cn_num)
                    if not num in category.keys():
                        category[num]=line
    # reorder keys
    category = dict(sorted(category.items()))

    return category

if __name__=="__main__":
    infile = 'shishuo.txt'
    category = cate_fetch(infile)
    print (category)
            #if not line[0].isdigit():
             #   print (line)
