#include <vector>
#include <map>
#include <algorithm>

// 牌型定义：万(1-9)、条(11-19)、饼(21-29)、风(31-34)、箭(35-37)
enum TileType {
    CHARACTER = 1,  // 万
    BAMBOO = 11,    // 条
    CIRCLE = 21,    // 饼
    WIND = 31,      // 风（东31,南32,西33,北34）
    DRAGON = 35     // 箭（中35,发36,白37）
};

class MahjongCore {
public:
    // 检查是否胡牌
    bool checkWin(const std::vector<int>& handTiles, int lastTile = -1) {
        std::vector<int> allTiles = handTiles;
        if (lastTile != -1) {
            allTiles.push_back(lastTile);
        }
        
        // 胡牌必须是14张牌
        if (allTiles.size() != 14) return false;
        
        // 排序便于检查
        std::sort(allTiles.begin(), allTiles.end());
        
        // 检查基本牌型：4组+1对
        return checkBasicPattern(allTiles);
    }
    
    // 计算番数
    int calculateFan(const std::vector<int>& handTiles, int lastTile = -1) {
        int fan = 0;
        
        // 检查清一色（24番）
        if (isPureColor(handTiles, lastTile)) {
            fan += 24;
        }
        
        // 检查碰碰胡（6番）
        if (isAllTriplets(handTiles, lastTile)) {
            fan += 6;
        }
        
        // 其他番种计算...
        
        // 国标麻将最低8番才能胡
        return fan >= 8 ? fan : 0;
    }

private:
    // 检查基本牌型
    bool checkBasicPattern(const std::vector<int>& tiles) {
        std::map<int, int> countMap;
        for (int tile : tiles) {
            countMap[tile]++;
        }
        
        // 尝试每一种可能的将牌（一对）
        for (auto& entry : countMap) {
            if (entry.second >= 2) {
                std::map<int, int> tempMap = countMap;
                tempMap[entry.first] -= 2;
                if (tempMap[entry.first] == 0) {
                    tempMap.erase(entry.first);
                }
                
                if (checkAllGroups(tempMap)) {
                    return true;
                }
            }
        }
        
        return false;
    }
    
    // 检查是否所有牌都能组成刻子或顺子
    bool checkAllGroups(std::map<int, int> tileCounts) {
        if (tileCounts.empty()) return true;
        
        int firstTile = tileCounts.begin()->first;
        int count = tileCounts[firstTile];
        
        // 尝试刻子（3张相同）
        if (count >= 3) {
            tileCounts[firstTile] -= 3;
            if (tileCounts[firstTile] == 0) {
                tileCounts.erase(firstTile);
            }
            
            if (checkAllGroups(tileCounts)) {
                return true;
            }
            
            // 回溯
            tileCounts[firstTile] += 3;
        }
        
        // 尝试顺子（仅适用于数牌）
        if (firstTile < WIND) {  // 万、条、饼
            int second = firstTile + 1;
            int third = firstTile + 2;
            
            if (tileCounts.find(second) != tileCounts.end() && 
                tileCounts.find(third) != tileCounts.end() &&
                tileCounts[firstTile] >= 1 &&
                tileCounts[second] >= 1 &&
                tileCounts[third] >= 1) {
                
                tileCounts[firstTile] -= 1;
                tileCounts[second] -= 1;
                tileCounts[third] -= 1;
                
                if (tileCounts[firstTile] == 0) tileCounts.erase(firstTile);
                if (tileCounts[second] == 0) tileCounts.erase(second);
                if (tileCounts[third] == 0) tileCounts.erase(third);
                
                if (checkAllGroups(tileCounts)) {
                    return true;
                }
                
                // 回溯
                tileCounts[firstTile] += 1;
                tileCounts[second] += 1;
                tileCounts[third] += 1;
            }
        }
        
        return false;
    }
    
    // 检查是否为清一色
    bool isPureColor(const std::vector<int>& handTiles, int lastTile) {
        std::vector<int> allTiles = handTiles;
        if (lastTile != -1) allTiles.push_back(lastTile);
        
        if (allTiles.empty()) return false;
        
        int type = getTileType(allTiles[0]);
        for (int tile : allTiles) {
            if (getTileType(tile) != type) {
                return false;
            }
        }
        return true;
    }
    
    // 获取牌的类型（万/条/饼/字）
    int getTileType(int tile) {
        if (tile >= DRAGON) return DRAGON;
        if (tile >= WIND) return WIND;
        if (tile >= CIRCLE) return CIRCLE;
        if (tile >= BAMBOO) return BAMBOO;
        return CHARACTER;
    }
    
    // 检查是否为碰碰胡
    bool isAllTriplets(const std::vector<int>& handTiles, int lastTile) {
        // 实现碰碰胡判定逻辑
        return false;
    }
};
    