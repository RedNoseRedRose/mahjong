import mahjong_core

def test_win():
    # 胡牌示例（顺子+刻子+对）
    tiles = [1,2,3,4,5,6,7,8,9,11,12,13,31,31]
    assert mahjong_core.is_win(tiles) == True

def test_not_win():
    # 非胡牌示例
    tiles = [1,1,1,2,2,2,3,3,3,4,4,4,5,6]
    assert mahjong_core.is_win(tiles) == True

def test_invalid_tile():
    # 非法牌面
    tiles = [0,2,3,4,5,6,7,8,9,11,12,13,31,31]
    assert mahjong_core.is_win(tiles) == False

def test_wrong_count():
    # 牌数不对
    tiles = [1,2,3]
    assert mahjong_core.is_win(tiles) == False

if __name__ == "__main__":
    test_win()
    test_not_win()
    test_invalid_tile()
    test_wrong_count()
    print("All tests passed.")