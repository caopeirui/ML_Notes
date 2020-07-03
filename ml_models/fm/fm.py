"""
FM因子分解机的简单实现，只实现了损失函数为平方损失的回归任务，更多功能扩展请使用后续的FFM
"""
import numpy as np
from tqdm import tqdm


class FM(object):
    def __init__(self, epochs=1, lr=1e-3, batch_size=2, hidden_dim=4, lamb=1e-3, alpha=1e-3, normal=True,
                 solver='adam', rho_1=0.9, rho_2=0.999):
        """

        :param epochs: 迭代轮数
        :param lr: 学习率
        :param batch_size:
        :param hidden_dim:隐变量维度
        :param lamb:l2正则项系数
        :param alpha:l1正则项系数
        :param normal:是否归一化，默认用min-max归一化
        :param solver:优化方式，包括sgd,adam,默认adam
        :param rho_1:adam的rho_1的权重衰减,solver=adam时生效
        :param rho_2:adam的rho_2的权重衰减,solver=adam时生效
        """
        self.epochs = epochs
        self.lr = lr
        self.batch_size = batch_size
        self.hidden_dim = hidden_dim
        self.lamb = lamb
        self.alpha = alpha
        self.solver = solver
        self.rho_1 = rho_1
        self.rho_2 = rho_2
        # 初始化参数
        self.w = None  # w_0,w_i
        self.V = None  # v_{i,f}
        # 归一化
        self.normal = normal
        if normal:
            self.xmin = None
            self.xmax = None

    def _y(self, X):
        """
        实现y(x)的功能
        :param X:
        :return:
        """
        # 去掉第一列bias
        X_ = X[:, 1:]
        X_V = X_ @ self.V
        X_V_2 = X_V * X_V
        X_2_V_2 = (X_ * X_) @ (self.V * self.V)
        pol = 0.5 * np.sum(X_V_2 - X_2_V_2, axis=1)
        return X @ self.w.reshape(-1) + pol

    def fit(self, X, y):
        if self.normal:
            self.xmin = X.min(axis=0)
            self.xmax = X.max(axis=0)
            X = (X - self.xmin) / self.xmax
        # 记录loss
        losses = []
        n_sample, n_feature = X.shape
        x_y = np.c_[np.ones(n_sample), X, y]
        # 调整一下学习率
        self.lr = max(self.lr, 1 / n_feature)
        # 初始化参数
        self.w = np.random.random((n_feature + 1, 1)) * 1e-3
        self.V = np.random.random((n_feature, self.hidden_dim)) * 1e-3
        if self.solver == 'adam':
            # 缓存梯度一阶，二阶估计
            w_1 = np.zeros_like(self.w)
            V_1 = np.zeros_like(self.V)
            w_2 = np.zeros_like(self.w)
            V_2 = np.zeros_like(self.V)
        # 更新参数
        count = 0
        for _ in tqdm(range(self.epochs)):
            np.random.shuffle(x_y)
            for index in tqdm(range(x_y.shape[0] // self.batch_size)):
                count += 1
                batch_x_y = x_y[self.batch_size * index:self.batch_size * (index + 1)]
                batch_x = batch_x_y[:, :-1]
                batch_y = batch_x_y[:, -1:]
                # 计算y(x)-t
                y_x_t = self._y(batch_x).reshape((-1, 1)) - batch_y
                # 更新w
                if self.solver == 'sgd':
                    self.w = self.w - (self.lr * (np.sum(y_x_t * batch_x, axis=0) / self.batch_size).reshape(
                        (-1, 1)) + self.lamb * self.w + self.alpha * np.where(self.w > 0, 1, 0))
                elif self.solver == 'adam':
                    w_reg = self.lamb * self.w + self.alpha * np.where(self.w > 0, 1, 0)
                    w_grad = (np.sum(y_x_t * batch_x, axis=0) / self.batch_size).reshape(
                        (-1, 1)) + w_reg
                    w_1 = self.rho_1 * w_1 + (1 - self.rho_1) * w_grad
                    w_2 = self.rho_2 * w_2 + (1 - self.rho_2) * w_grad * w_grad
                    w_1_ = w_1 / (1 - np.power(self.rho_1, count))
                    w_2_ = w_2 / (1 - np.power(self.rho_2, count))
                    self.w = self.w - (self.lr * w_1_) / (np.sqrt(w_2_) + 1e-8)

                # 更新 V
                batch_x_ = batch_x[:, 1:]
                V_X = batch_x_ @ self.V
                X_2 = batch_x_ * batch_x_
                # 从i,f单个元素逐步更新有点慢
                # for i in range(self.V.shape[0]):
                #     for f in range(self.V.shape[1]):
                #         if self.solver == "sgd":
                #             self.V[i, f] -= self.lr * (
                #                 np.sum(y_x_t.reshape(-1) * (batch_x_[:, i] * V_X[:, f] - self.V[i, f] * X_2[:, i]))
                #                 / self.batch_size + self.lamb * self.V[i, f] + self.alpha * (self.V[i, f] > 0))
                #         elif self.solver == "adam":
                #             v_reg = self.lamb * self.V[i, f] + self.alpha * (self.V[i, f] > 0)
                #             v_grad = np.sum(y_x_t.reshape(-1) * (
                #                 batch_x_[:, i] * V_X[:, f] - self.V[i, f] * X_2[:, i])) / self.batch_size + v_reg
                #             V_1[i, f] = self.rho_1 * V_1[i, f] + (1 - self.rho_1) * v_grad
                #             V_2[i, f] = self.rho_2 * V_2[i, f] + (1 - self.rho_2) * v_grad * v_grad
                #             v_1_ = V_1[i, f] / (1 - np.power(self.rho_1, count))
                #             v_2_ = V_2[i, f] / (1 - np.power(self.rho_2, count))
                #             self.V[i, f] = self.V[i, f] - (self.lr * v_1_) / (np.sqrt(v_2_) + 1e-8)

                # 从隐变量的维度进行更新
                for f in range(self.V.shape[1]):
                    if self.solver == 'sgd':
                        V_grad = np.sum(
                            y_x_t.reshape((-1, 1)) * (batch_x_ * V_X[:, f].reshape((-1, 1)) - X_2 * self.V[:, f]),
                            axis=0)
                        self.V[:, f] = self.V[:, f] - self.lr * V_grad - self.lamb * self.V[:, f] - self.alpha * (
                            self.V[:, f] > 0)
                    elif self.solver == 'adam':
                        V_reg = self.lamb * self.V[:, f] + self.alpha * (self.V[:, f] > 0)
                        V_grad = np.sum(
                            y_x_t.reshape((-1, 1)) * (batch_x_ * V_X[:, f].reshape((-1, 1)) - X_2 * self.V[:, f]),
                            axis=0) + V_reg
                        V_1[:, f] = self.rho_1 * V_1[:, f] + (1 - self.rho_1) * V_grad
                        V_2[:, f] = self.rho_2 * V_2[:, f] + (1 - self.rho_2) * V_grad * V_grad
                        V_1_ = V_1[:, f] / (1 - np.power(self.rho_1, count))
                        V_2_ = V_2[:, f] / (1 - np.power(self.rho_2, count))
                        self.V[:, f] = self.V[:, f] - (self.lr * V_1_) / (np.sqrt(V_2_) + 1e-8)

                # 计算loss
                loss = np.sum(np.abs(y - self.predict(X))) / n_sample
                losses.append(loss)
        return losses

    def predict(self, X):
        """
        :param X:
        :return:
        """
        if self.normal:
            X = (X - self.xmin) / self.xmax
        n_sample, n_feature = X.shape
        X_V = X @ self.V
        X_V_2 = X_V * X_V
        X_2_V_2 = (X * X) @ (self.V * self.V)
        pol = 0.5 * np.sum(X_V_2 - X_2_V_2, axis=1)
        return np.c_[np.ones(n_sample), X] @ self.w.reshape(-1) + pol
