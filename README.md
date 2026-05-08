# BasicThings
基础模板仓库。

# 分支功能
使用commitizen,commitlint,husky,git-cliff进行md管理。

# 提醒
推荐在全局 Git 配置中加入 [alias] cz = "!git-cz"，之后就可以直接使用 git cz 代替 npm run commit 或 npx git-cz。

# 流程
提交：git cz  
查看推荐的版本：git cliff --bump  
固定版本：git tag x.x.x  
生成changelog：git cliff -o  
提交changelog更新：git cz (doc)  
推送：git push  