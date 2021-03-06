from keras.preprocessing import sequence
from keras.utils import np_utils
from keras.models import Sequential, Graph
from keras.layers.core import Dense, Dropout, Activation, Lambda, Merge, Masking
from keras.layers.embeddings import Embedding
from keras.layers.recurrent import LSTM, GRU
from keras.callbacks import ModelCheckpoint, EarlyStopping
# from keras.utils.visualize_util import plot
import theano

import sys
import numpy as np
import pdb

if __name__ == '__main__':
	
	# for processing the data, of course
	# if it's the training file, generates the vocabulary list. Else we have to pass the vocabulary list 
	# @entity1 - @entity1000 is part of vocab, hopefully it doesn't go beyond that
	
	train_file = '/home/ee/btech/ee1130504/data/cnn_training_set.txt'
	valid_file = '/home/ee/btech/ee1130504/data/cnn_validation_set.txt'
	test_file = '/home/ee/btech/ee1130504/data/cnn_test_set.txt'
	
	def process_data(file, training_data = True, vocab = None, vocab_size = None):
		f = open(file)                        
		raw_data = f.readlines()
		input_doc = []                        # list of list of words in doc
		input_query = []                      # list of list of words in query
		target_word = []                      # list of target words
		# vocab = {}                            # vocabulary => yeh bahut galat kiya aapne
		url = []             				  # list of urls, mostly useless
		entity_list = []                    # entity listing for each doc, mostly useless
		vocab_limit = 50000                   # Will depend on training data
		i = 0

		while i <len(raw_data):
			url.append(raw_data[i].strip('\n'))
			i += 2
			input_doc.append(raw_data[i].strip('\n').split(' '))
			i += 2
			input_query.append(raw_data[i].strip('\n').split(' '))
			i += 2
			target_word.append(raw_data[i].strip('\n'))
			i += 2
			entity_list.append([])
			while(raw_data[i] != '\n'):
				# entity_list[-1].append(raw_data[i].strip('\n'))
				i += 1
			i += 2
		# l = {}
		
		if not vocab:
			vocab = {}
			for doc in input_doc + input_query:
				for word in doc:
					# if(word.startswith('@entity')):
					# 	l[word[7:]] = 1
					if word not in vocab:
						vocab[word] = 1
					else:
						vocab[word] += 1
			# print sorted([int(m) for m in l])
			vocablist = vocab.items()
			vocablist.sort(key = lambda t: -t[1])
			vocab = {}
			vocab_size = 0
		
			vocab['@placeholder'] = 2
			for j in range(1000):
				vocab['@entity' + str(j)] = j + 3
			vocab_size = 1003
			for word in vocablist:
				if word[0] in vocab:
					continue
				if(vocab_size >= vocab_limit):
					vocab[word[0]] = 1  #reserve 1 for OOV, reserve 0 for padding
				else:
					vocab[word[0]] = vocab_size
					vocab_size += 1
			vocab['#delim'] = vocab_size
			vocab_size += 1

		for i, doc in enumerate(input_doc):
			for j, word in enumerate(doc):
				if word in vocab:
					input_doc[i][j] = vocab[word]
				else:
					input_doc[i][j] = 1

		for i, query in enumerate(input_query):
			for j, word in enumerate(query):
				if word in vocab:
					input_query[i][j] = vocab[word]
				else:
					input_query[i][j] = 1
		target_word = [vocab[word] for word in target_word]  #assuming every entity is in vocab
		#for Deep reader
		# inputs = [query + [vocab['#delim']] + doc for doc, query in zip(input_doc, input_query)]
		return input_doc, input_query, target_word, vocab, vocab_size

	train_input_doc, train_input_query, train_target_word, vocab, vocab_size = process_data(train_file)
	valid_input_doc, valid_input_query, valid_target_word, vocab, vocab_size = process_data(valid_file, False, vocab, vocab_size)
	test_input_doc, test_input_query, test_target_word, vocab, vocab_size = process_data(test_file, False, vocab, vocab_size)

	maxlen = 2000
	# frac = 0.8
	train_inputs = [query + [vocab['#delim']] + doc for doc, query in zip(train_input_doc, train_input_query)]
	valid_inputs = [query + [vocab['#delim']] + doc for doc, query in zip(valid_input_doc, valid_input_query)]
	test_inputs = [query + [vocab['#delim']] + doc for doc, query in zip(test_input_doc, test_input_query)]

	batch_size = 256  #change as gpu memory allows
	
	#generator for training data, hopefully understandable
	def generate_training_batches():
		index = 0         #IF I understand correctly, state of index will be saved because it's local
		while True:
			remaining = len(train_inputs) - index
			input_slice = []
			target_slice = []
			if remaining >= batch_size:
				input_slice = train_inputs[index:(index + batch_size)]
				target_slice = train_target_word[index:(index + batch_size)]
				index += batch_size
			else:
				input_slice = train_inputs[index:]
				input_slice += train_inputs[:(batch_size - remaining)]
				target_slice = train_target_word[index:]
				target_slice += train_target_word[:(batch_size - remaining)]
				index = batch_size - remaining
			x_train = sequence.pad_sequences(input_slice, maxlen = maxlen)
			y_train = np.zeros((batch_size, vocab_size))
			#pdb.set_trace()
			y_train[np.arange(batch_size), np.array(target_slice)] = 1
			yield {'input': x_train, 'output': y_train}

	#because I don't know how to use one function for training, valid and test
	def generate_valid_batches():
		index = 0
		while True:
			remaining = len(valid_inputs) - index
			input_slice = []
			target_slice = []
			if remaining >= batch_size:
				input_slice = valid_inputs[index:(index + batch_size)]
				target_slice = valid_target_word[index:(index + batch_size)]
				index += batch_size
			else:
				input_slice = valid_inputs[index:]
				input_slice += test_inputs[:(batch_size - remaining)]
				target_slice = valid_target_word[index:]
				target_slice += valid_target_word[:(batch_size - remaining)]
				index = batch_size - remaining
			x_valid = sequence.pad_sequences(input_slice, maxlen = maxlen)
			y_valid = np.zeros((batch_size, vocab_size))
			y_valid[np.arange(batch_size), np.array(target_slice)] = 1
			yield {'input': x_valid, 'output': y_valid}

	def generate_test_batches():
		index = 0
		while True:
			remaining = len(test_inputs) - index
			input_slice = []
			target_slice = []
			if remaining >= batch_size:
				input_slice = test_inputs[index:(index + batch_size)]
				target_slice = test_target_word[index:(index + batch_size)]
				index += batch_size
			else:
				input_slice = test_inputs[index:]
				input_slice += test_inputs[:(batch_size - remaining)]
				target_slice = test_target_word[index:]
				target_slice += test_target_word[:(batch_size - remaining)]
				index = batch_size - remaining
			x_test = sequence.pad_sequences(input_slice, maxlen = maxlen)
			y_test = np.zeros((batch_size, vocab_size))
			y_test[np.arange(batch_size), np.array(target_slice)] = 1
			yield {'input': x_test, 'output': y_test}

	def get_y_T(X):
		return X[:, -1, :]

	samples_per_epoch = 25600
	nb_epoch = int((len(train_inputs)/float(samples_per_epoch))*10)

	model = Graph()
	model.add_input(name = 'input', input_shape = (maxlen,), dtype = 'int')
	model.add_node(Embedding(vocab_size,256, input_length=maxlen, dropout=0.1), input='input', name='emb')
	model.add_node(LSTM(128, dropout_W=0.1, dropout_U=0.1, return_sequences = True), input = 'emb', name = 'lstm1')
	model.add_node(Dropout(0.1), input = 'lstm1', name = 'dropout1')
	model.add_node(LSTM(128, dropout_W=0.1, dropout_U=0.1), input = 'dropout1', name = 'lstm2')
	model.add_node(Dropout(0.1), input = 'lstm2', name = 'dropout2')
	model.add_node(Lambda(get_y_T, output_shape = (128,)), input = 'dropout1', name = 'slice')
	model.add_node(Dense(vocab_size), inputs = ['slice', 'dropout2'], name = 'dense', merge_mode = 'concat', concat_axis = 1)
	model.add_node(Activation('softmax'), input = 'dense', name = 'softmax')
	model.add_output(name='output', input='softmax')
	print model.summary()
	model.compile(loss = {'output': 'categorical_crossentropy'}, optimizer = 'rmsprop')
	# plot(model, to_file='model2.png', show_shape = True)
	print('Train...')
	# plot(model, to_file='model.png', show_shape = True)

	#stuff that can be changed:
	#patience: number of continuous epochs for which validation loss does not decrease after which to stop training
	#samples_per_epoch: batch_size * samples_per_epoch is the number of training examples seen per epoch..
	#.. model is saved to file after one epoch
	#nb_epoch: Because of Early Stopping this is set to a large number for now
	#model_path: Folder in which models will be saved <- create this folder

	callbacks = []
	model_path = '/home/ee/btech/ee1130504/Models/DeepReader/'
	callbacks.append(ModelCheckpoint(model_path + 'model_weights.{epoch:02d}-{val_loss:.3f}.hdf5', verbose = 1))
	callbacks.append(EarlyStopping(patience = 10))
	model.fit_generator(generate_training_batches(), samples_per_epoch = samples_per_epoch, nb_epoch = nb_epoch, validation_data = generate_valid_batches(), nb_val_samples = len(valid_inputs) , callbacks = callbacks, show_accuracy = True)
	score, acc = model.evaluate_generator(generate_test_batches(), nb_val_samples = len(test_inputs) , show_accuracy = True)
	print('Test score:', score)
	print('Test accuracy:', acc)
