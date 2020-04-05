#define PY_SSIZE_T_CLEAN
#include <string>
#include <array>
#include <vector>
#include <utility>
#include <stack>
#include <tuple>
#include <map>
#include <set>
#include <queue>
#include <algorithm>
#include <compare>
#include <functional>
#include <exception>
#include <Python.h>

using namespace std;

struct BlockPos {
	int row;
	int column;
#ifdef __cpp_lib_three_way_comparison
	auto operator<=>(const BlockPos&) const = default;
#else
	bool operator==(const BlockPos&) const = default;
	bool operator<(const BlockPos&) const = default;
#endif
};

struct SidePos {
	int row;
	int column;
	bool isDown;
};

struct SideInitException : public exception {
	SideInitException(SidePos side) : side(side) {};
	SidePos side;
};

struct Block {
	enum BlockStatus { Empty, Crossed, Pinned, Connected } status;
	int area = -1;
};

struct Side {
	enum SideStatus { Null, Empty, Crossed, Pinned } status;
	//pair<Block*, Block*> block = { nullptr, nullptr }; // sorted by area
	//pair<int, int> area() { return make_pair(block.first->area, block.second->area); }
};

class Board {
public:
	Board(int size, vector<vector<bool>> side_row, vector<vector<bool>> side_column,
		vector<int> count_row, vector<int> count_column, int needed = 1);
	~Board() = default;
	Side& getSide(const SidePos side) const { return sides[side.row][side.column][int(side.isDown)]; }
	Block& getBlock(const BlockPos pos) const { return blocks[pos.row][pos.column]; }
	vector<SidePos> findSides(const BlockPos pos) const;
	vector<SidePos> findEmptySides(const BlockPos pos) const;
	pair<BlockPos, BlockPos> findBlocks(const SidePos side) const;
	BlockPos findAcross(const SidePos side, const BlockPos pos) const;
private:
	int size;
	int needed;
	vector<vector<Block>> blocks;
	vector<vector<array<Side, 2>>> sides; // first right, next down
	map<pair<int, int>, set<SidePos>> sides_bucket; // key need to be ordered!
	map<pair<int, int>, int> sides_left; // key need to be ordered!
	vector<int> row_left;
	vector<int> column_left;
	vector<int> row_max;
	vector<int> column_max;
	void setCrossed(const BlockPos pos); // set the block and adjecant sides crossed
	void setCrossed(const SidePos side); // set side crossed
	void setPin(const BlockPos pos); // set the pin and decrease counts
	void setConnected(const SidePos side); // set two pins
	// returns true if something changed
	bool checkCount(); // check for zero or one or max-1 or max in row_left and column_left
	bool checkBlock(); // check for any pin has only one empty side or any block has no empty side
	bool checkArea(); // check for any area border has only $needed$ empty side left(or some thing can be determined)
};

template<typename T>
#ifdef __cpp_lib_concepts
	requires Compare<T>
#endif
pair<set<T>, set<T>> MinVertexCover(const set<pair<T, T>>& f);

Board::Board(int size, vector<vector<bool>> side_row, vector<vector<bool>> side_column,
	vector<int> count_row, vector<int> count_column, int needed) :
	size(size), blocks(size, vector<Block>(size, Block())), row_left(move(count_row)), column_left(move(count_column)),
	row_max(size, size), column_max(size, size),
	sides(size, vector<array<Side, 2>>(size, array<Side, 2>{ Side(), Side() })) {
	// assign sides
	for (int row = 0; row < size; ++row)
		for (int column = 0; column < size; ++column) {
			if (column != size - 1 && side_row[row][column])
				sides[row][column][0].status = Side::Empty;
			if (row != size - 1 && side_column[row][column])
				sides[row][column][1].status = Side::Empty;
		}
	// divide areas
	int area_count = 0;
	for (int row = 0; row < size; ++row)
		for (int column = 0; column < size; ++column) {
			if (blocks[row][column].area == -1) {
				blocks[row][column].area = area_count;
				stack<BlockPos> todo;
				todo.push(BlockPos{ row, column });
				while (!todo.empty()) {
					auto pos = todo.top();
					todo.pop();
					for (auto& b : findSides(pos)) {
						auto& s = getSide(b);
						auto across = (b.row != row || b.column != column) ? BlockPos{ b.row, b.column } :
							b.isDown ? BlockPos{ b.row + 1, b.column } : BlockPos{ b.row, b.column + 1 };
						if (s.status == Side::Null) {
							if (int& a = getBlock(across).area; a == -1) {
								a = area_count;
								todo.push(across);
							}
							else if (a != area_count)
								throw SideInitException(b);
						}
						else if (getBlock(across).area == area_count)
							throw SideInitException(b);
					}
				}
				area_count++;
			}
		}
	// assign block to sides and construct size bucket
	for (int row = 0; row < size; ++row)
		for (int column = 0; column < size; ++column) {
			auto& s = sides[row][column];
			/*auto f = [](Block* block1, Block* block2) {
				if (block1->area < block2->area)
					return make_pair(block1, block2);
				else
					return make_pair(block2, block1);
			};*/
			auto a = [](const Block& block1, const Block& block2) {
				return make_pair(min(block1.area, block2.area), max(block1.area, block2.area));
			};
			if (s[0].status != Side::Null) {
				//s[0].block = f(&blocks[row][column], &blocks[row][column + 1]);
				auto area = a(&[row][column], blocks[row][column + 1]);
				if (sides_bucket.count(area) == 0)
					sides_bucket[area] = set<SidePos>{ SidePos{ row, column, false } };
				else
					sides_bucket[area].insert(SidePos{ row, column, false });
			}
			if (s[1].status != Side::Null) {
				//s[1].block = f(&blocks[row][column], &blocks[row + 1][column]);
				auto area = a(blocks[row][column], blocks[row + 1][column]);
				if (sides_bucket.count(area) == 0)
					sides_bucket[area] = set<SidePos>{ SidePos{ row, column, true } };
				else
					sides_bucket[area].insert(SidePos{ row, column, true });
			}
		}
	for (auto& [key, val] : sides_bucket)
		sides_left[key] = needed;
}

vector<SidePos> Board::findSides(const BlockPos pos) const
{
	vector<SidePos> v;
	if (pos.row != 0) // UP
		v.push_back(SidePos{ pos.row - 1, pos.column, true });
	if (pos.column != 0) // LEFT
		v.push_back(SidePos{ pos.row, pos.column - 1, false });
	if (pos.row != size - 1) //DOWN
		v.push_back(SidePos{ pos.row, pos.column, true });
	if (pos.column != size - 1) //RIGHT
		v.push_back(SidePos{ pos.row, pos.column, false });
	return v;
}

vector<SidePos> Board::findEmptySides(const BlockPos pos) const
{
	vector<SidePos> v, v2 = findSides(pos);
	copy_if(v2.begin(), v2.end(), back_inserter(v), [&s = this->sides](SidePos t) {
		return s[t.row][t.column][int(t.isDown)].status == Side::Empty;
	});
	return v;
}

pair<BlockPos, BlockPos> Board::findBlocks(const SidePos side) const
{
	return { BlockPos{side.row, side.column}, side.isDown ? BlockPos{side.row + 1, side.column} : BlockPos{side.row, side.column + 1} };
}

BlockPos Board::findAcross(const SidePos side, const BlockPos pos) const {
	auto [b1, b2] = findBlocks(side);
	return b1 == pos ? b2 : b1;
}

void Board::setCrossed(const BlockPos pos) {
	getBlock(pos).status = Block::Crossed;
	for (auto& p : findEmptySides(pos)) {
		getSide(p).status = Side::Crossed;
	}
	row_max[pos.row]--;
	column_max[pos.column]--;
}
void Board::setCrossed(const SidePos side) {
	getSide(side).status = Side::Crossed;
}
void Board::setPin(const BlockPos pos) {
	getBlock(pos).status = Block::Pinned;
	row_left[pos.row]--;
	column_left[pos.column]--;
	row_max[pos.row]--;
	column_max[pos.column]--;
}
void Board::setConnected(const SidePos side) {
	auto& side2 = getSide(side);
	side2.status = Side::Pinned;
	pair<int, int> m{ INT_MAX, -1 };
	for (auto& block : findBlocks(side)) {
		auto b = getBlock(block);
		m.first = min(m.first, b.area);
		m.second = max(m.second, b.area);
		if (b.status == Block::Empty){
			row_left[block.row]--;
			column_left[block.column]--;
			row_max[block.row]--;
			column_max[block.column]--;
		}
		b.status = Block::Connected;
		for (auto& p : findEmptySides(block)) {
			getSide(p).status = Side::Crossed;
		}
	}
	sides_left[m] -= 1;
}

bool Board::checkCount() {
	bool flag = false;
	for (int row = 0; row < size; ++row) {
		auto& count = row_left[row];
		if (count < 0 || count > row_max[row]) {
			// error
		}
		else if (count == 0) {
			for (int column = 0; column < size; ++column)
				if (blocks[row][column].status == Block::Empty) {
					setCrossed(BlockPos{ row, column });
					flag = true;
				}
		}
		else if (count == row_max[row]) {
			for (int column = 0; column < size; ++column)
				if (blocks[row][column].status == Block::Empty) {
					setPin(BlockPos{ row, column });
					flag = true;
				}
		}
		else {
			if (count == 1)
				for (int column = 0; column < size; ++column)
					if (sides[row][column][0].status == Side::Empty) {
						SidePos s{ row, column, false };
						if (auto b2 = findBlocks(s); getBlock(b2[0]).status == Block::Empty && getBlock(b2[1]).status == Block::Empty) {
							setCrossed(s);
							flag = true;
						}
					}
			if (count == row_max[row] - 1)
				for (int column = 0; column < size; ++column)
					if (auto e = findEmptySides(BlockPos{ row, column }); e.size() == 1 && e[0].isDown == false) {
						auto p = e[0];
						auto across = (p.column == column ? BlockPos{ p.row, p.column + 1 } : BlockPos{ p.row, p.column });
						if (getBlock(across).status == Block::Empty) {
							setPin(across);
							flag = true;
						}
					}
		}
	}
	for (int column = 0; column < size; ++column) {
		auto& count = column_left[row];
		if (count < 0 || count > column_max[column]) {
			// error
		}
		else if (count == 0) {
			for (int row = 0; row < size; ++row)
				if (blocks[row][column].status == Block::Empty) {
					setCrossed(BlockPos{ row, column });
					flag = true;
				}
		}
		else if (count == column_max[column]) {
			for (int row = 0; row < size; ++row)
				if (blocks[row][column].status == Block::Empty) {
					setPin(BlockPos{ row, column });
					flag = true;
				}
		}
		else {
			if (count == 1)
				for (int row = 0; row < size; ++row)
					if (sides[row][column][1].status == Side::Empty) {
						SidePos s{ row, column, true };
						if (auto b2 = findBlocks(s); getBlock(b2[0]).status == Block::Empty && getBlock(b2[1]).status == Block::Empty) {
							setCrossed(s);
							flag = true;
						}
					}
			if (count == column_max[column] - 1)
				for (int row = 0; row < size; ++row)
					if (auto e = findEmptySides(BlockPos{ row, column }); e.size() == 1 && e[0].isDown == true) {
						auto p = e[0];
						auto across = (p.row == row ? BlockPos{ p.row + 1, p.column } : BlockPos{ p.row, p.column });
						if (getBlock(across).status == Block::Empty) {
							setPin(across);
							flag = true;
						}
					}
		}
	}
	return flag;
}
bool Board::checkBlock() {
	bool flag = false;
	for (int row = 0; row < size; ++row)
		for (int column = 0; column < size; ++column) {
			if (auto block = blocks[row][column]; block.status == Block::Pinned) {
				if (auto e = findEmptySides(BlockPos{ row, column }); e.size() == 0) {
					// error
				}
				else if (e.size() == 1) {
					setConnected(e[0]);
					flag = true;
				}
			}
			else if (block.status == Block::Empty && findEmptySides(BlockPos{ row, column }).empty()) {
				setCrossed(BlockPos{ row, column });
				flag = true;
			}
		}
	return flag;
}
bool Board::checkArea() {
	bool flag = false;
	auto a = [this](const SidePos& pos) {
		auto [p1, p2] = this->findBlocks(pos);
		if (this->getBlock(p1).area < this->getBlock(p2).area)
			return make_pair(p1, p2);
		else
			return make_pair(p2, p1);
	};
	for (auto& [areas, st] : sides_bucket) {
		if (sides_left[areas] < 0) {
			// error
		}
		if (st.empty())
			continue;
		set<pair<BlockPos, BlockPos>> st2;
		transform(st.begin(), st.end(), inserter(st2), a);
		auto& [sl, sr] = MinVertexCover(st2);
		if (sl.size() + sr.size() < sides_left[areas]) {
			// error
		}
		else if (sl.size() + sr.size() == sides_left[areas]) {
			for (auto& pos : sl) {
				setPin(pos);
				for (auto& side : findEmptySides(pos))
					if (auto b = findAcross(side, pos); b.area != areas.first && b.area != areas.second)
						setCrossed(side);
			}
			for (auto& pos : sr) {
				setPin(pos);
				for (auto& side : findEmptySides(pos))
					if (auto b = findAcross(side, pos); b.area != areas.first && b.area != areas.second)
						setCrossed(side);
			}
			flag = true;
		}
	}
	return flag;
}

template<typename T>
pair<set<T>, set<T>> MinVertexCover(const set<pair<T, T>>& sides) {
	//array<map<T, vector<T>>, 2> vertex;
	map<T, vector<T>> vertex_l;
	map<T, T> match; // left to right and right to left
	for (auto& [s1, s2] : sides) {
		if (auto it = vertex_l.find(s1); it != vertex_l.end())
			it->second.push_back(s2);
		else
			vertex_l.emplace(s1, vector<T>{ s2 });
		//if (auto it = vertex[1].find(s2); it != vertex[1].end())
		//	it->second.push_back(s1);
		//else
		//	vertex[1].emplace(s2, vector<T>{ s1 });
	}
	//queue<T> q;
	//transform(vertex[0].begin(), vertex[0].end(), inserter(q), [](pair<T, vector<T>> t) { return t.first; });
	map<T, T> tags;
	//while (!q.empty()) {
	for (auto& l : vertex_l) {
		//auto l = q.front(); q.pop();
		for (auto& r : vertex_l) {
			if (auto it = match.find(r); it == match.end()) {
				match[r] = l;
				match[l] = r;
				auto l2 = l;
				auto it2 = tags.find(l2);
				while (it2 != tags.end()) {
					l2 = tags[it2->second];
					match[it2->second] = l2;
					match[l2] = it2->second;
					it2 = tags.find(l2);
				}
				tags = map<T, T>();
				break;
			}
			else if (it->second != l && !tags.contains(r)) {
				tags[r] = l;
				tags[it->second] = r;
				q.push(it->second);
			}
		}
	}

	pair<set<T>, set<T>> cover;
	pair<set<T>, set<T>> todo;
	for (auto& [t, v] : vertex_l) {
		if (!match.contains(t))
			todo.first.insert(t);
		cover.first.insert(t);
	}
	while (todo.first.size() != 0) {
		for (auto& l : todo.first) {
			for (auto it = match.find(l); auto& r : vertex_l[l])
				if (!cover.second.contains(r) && (it == match.end() || it->second != r))
					todo.second.insert(r);
			cover.first.erase(l);
		}
		todo.first.clear();
		for (auto& r : todo.second) {
			if (cover.first.contains(match[r]))
				todo.first.insert(match[r]);
			cover.second.insert(r);
		}
		todo.second.clear();
	}
	return cover;
}


static PyObject* test(PyObject* self, PyObject* args) {
	const char* str;
	int sts;
	if (!PyArg_ParseTuple(args, "s", &str))
		return NULL;
	string s(str);
	sts = s.length();
	return PyLong_FromLong(sts);
}

static PyMethodDef Methods[] = {
	{"test", test, METH_VARARGS, "return the length of the string."},
	{NULL, NULL, 0, NULL}
};

static struct PyModuleDef stitchesmodule = {
	PyModuleDef_HEAD_INIT,
	"stitches",
	NULL,
	-1,
	Methods
};

PyMODINIT_FUNC
PyInit_stitches(void) {
	return PyModule_Create(&stitchesmodule);
}
