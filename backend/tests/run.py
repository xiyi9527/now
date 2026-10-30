"""
测试运行入口
用法:
  python -m tests.run           # 运行全部测试
  python -m tests.run auth      # 只跑认证模块
  python -m tests.run nsga2     # 只跑 NSGA-II 模块
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    modules = [
        "tests.test_auth",
        "tests.test_plan",
        "tests.test_tip",
        "tests.test_rating",
        "tests.test_plaza",
        "tests.test_nsga2",
    ]

    # 支持过滤：python -m tests.run nsga2 plaza
    filters = [a.lower() for a in sys.argv[1:]]
    if filters:
        modules = [m for m in modules if any(f in m for f in filters)]

    for mod in modules:
        try:
            suite.addTests(loader.loadTestsFromName(mod))
        except Exception as e:
            print(f"[WARN] 加载 {mod} 失败: {e}")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
