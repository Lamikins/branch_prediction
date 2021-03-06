import collections

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim


class BpPerceptron():
    """
    Wrapper for perceptron. Essentially just has logic for training
    """
    def __init__(self, n):
        self.net = ClassicalPerceptron(n)
        self.optimizer = optim.SGD(self.net.parameters(), lr=1e-3)

    def predict(self, X):
        pred = self.net(torch.tensor(X, dtype=torch.float))

        return pred

    def predict_and_update(self, X, y):
        self.optimizer.zero_grad()

        pred = self.predict(X)
        loss = torch.abs(pred - y)

        #Backpropagate
        loss.backward()
        self.optimizer.step()

        return (pred > 0.5).numpy()

class BpLambdaPerceptron():
    """
    Wrapper for perceptron. Essentially just has logic for training
    """
    def __init__(self, n, lamb):
        self.net = ClassicalPerceptron(n)
        self.optimizer = optim.SGD(self.net.parameters(), lr=1e-3)
        self.example_history_x = []
        self.example_history_y = []
        self.lamb = lamb
        self.bs = 16

    def predict(self, X):
        pred = self.net(torch.tensor(X, dtype=torch.float))

        return pred

    def learning_round(self):
        self.optimizer.zero_grad()
        
        rand_idxs = np.random.choice(np.arange(len(self.example_history_x)), 
            size=self.bs, replace=False)

        batch_x = torch.tensor(self.example_history_x,dtype=torch.float32)[rand_idxs]
        batch_y = torch.tensor(self.example_history_y,dtype=torch.float32)[rand_idxs]

        preds = self.predict(batch_x)

        preval = 2*batch_y - 1
        lambda_term = (self.lamb * torch.sum(batch_x**2,1) * preval).view(-1,1)

        #mask = lambda_term < preds

        loss = torch.mean(  torch.abs(preds-batch_y.view(-1,1)))

        loss.backward()
        self.optimizer.step()

    def predict_and_update(self, X, y):
        self.optimizer.zero_grad()

        if list(X) in self.example_history_x:
            preval = (2*self.example_history_y[self.example_history_x.index( list(X) )] )- 1
            #print(preval, np.sum(X**2))
            lambda_term = self.lamb * np.sum(X**2) * preval
            #print(lambda_term)
        else:
            lambda_term = 0

        
        pred = self.predict(X)
        loss = torch.abs(pred - y)

        if (len(self.example_history_x)+1) % (self.bs+1) == 0:
            self.learning_round()

        #Backpropagate
        loss.backward()
        self.optimizer.step()

        if (( (pred+lambda_term) > 0.5).numpy() != y):
            self.example_history_x.append(list(X))
            self.example_history_y.append(y)

        return ( (pred+lambda_term) > 0.5).numpy()


class ClassicalPerceptron(nn.Module):
    def __init__(self, n):
        super(ClassicalPerceptron, self).__init__()
        self.fc1 = nn.Linear(n,1)

    def forward(self, x):
        x = self.fc1(x)
        return x


class TruePerceptron():
    def __init__(self, n, eta=1):
        self.n = n
        self.eta = eta
        self.weights = np.zeros((self.n + 1,))

    def predict(self, X):
        pred = np.dot(self.weights[:self.n], X) + self.weights[self.n]

        return pred

    def predict_and_update(self, X, y):
        x_scale = 2 * X - 1
        y_scale = 2 * y - 1

        pred = self.predict(x_scale)
        pred = np.sign(pred)
        if pred != y_scale:
            self.weights[:self.n] += self.eta * y_scale * x_scale
            self.weights[self.n] += self.eta * y_scale

        return (np.sign(pred) + 1) / 2


class BranchPredictor():
    def __init__(self, n, preceptron=BpPerceptron, *argv):
        """
        This class is responsible for storing the table of perceptrons and
        keeping track of the global history register.
        """
        self.global_history = np.zeros((n,))
        self.total = collections.defaultdict(int)
        self.correct = collections.defaultdict(int)
        self.moving_accuracy = collections.defaultdict(float)
        self.taken_history = collections.defaultdict(list)
        self.prediction_history = collections.defaultdict(list)
        self.perceptrons = collections.defaultdict(lambda : preceptron(n, *argv))

    def __call__(self, condition, tag=None):
        """
        This is essentially the wrapper for the if statement or while condition

        If it is given a tag then it will make a prediction, if not it will
        just update the global history register
        """
        if tag:
            self.total[tag] += 1
            p = self.perceptrons[tag].predict_and_update(self.global_history,
                                                         int(condition))
            self.moving_accuracy[tag] *= 0.9

            self.taken_history[tag].append(1 if condition else 0)
            self.prediction_history[tag].append(1 if p else 0)

            if (condition == p):
                self.correct[tag] += 1
                self.moving_accuracy[tag] += 0.1

        self.update_history(condition)

        return condition

    def update_history(self, condition):
        """
        Appends the condition to the global history register
        """
        self.global_history = np.roll(self.global_history, 1)
        if condition:
            self.global_history[0] = 1
        else:
            self.global_history[0] = 0

    def print_accuracies(self):
        for key in self.perceptrons:
            acc = self.correct[key] / self.total[key]
            mv = self.moving_accuracy[key]
            print(f"Branch: {key} Accuracy {acc} Moving {mv}")

    def get_accuracies(self):
        acc = {}
        for key in self.perceptrons:
            acc[key] = self.correct[key] / self.total[key]
        return acc, self.moving_accuracy


if __name__ == "__main__":
    bp = BranchPredictor(10)

    i = 0
    i_max = 1000
    while bp(i < i_max, "condition"):
        if bp(np.random.random((1)) > 0.5, "random"):
            pass

        i+= 1

    bp.print_accuracies()
