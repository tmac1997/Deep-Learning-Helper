import pandas as pd
import numpy as np

from collections import OrderedDict

import torch
import torch.nn.functional as F

from torch import nn
from torch.autograd import Variable

from torch import nn

def show_summary(model, input_size=(3, 224, 224)):

    def get_names_dict(model):
        """
        Recursive walk to get names including path
        """
        names = {}
        def _get_names(module, parent_name=''):
            for key, module in module.named_children():
                name = parent_name + '.' + key if parent_name else key
                names[name]=module
                if isinstance(module, torch.nn.Module):
                    _get_names(module, parent_name=name)
        _get_names(model)
        return names


    def torch_summarize_df(input_size, model, weights=False, input_shape=True, nb_trainable=False):
        """
        Summarizes torch model by showing trainable parameters and weights.
        
        author: wassname
        url: https://gist.github.com/wassname/0fb8f95e4272e6bdd27bd7df386716b7
        license: MIT
        
        Modified from:
        - https://github.com/pytorch/pytorch/issues/2001#issuecomment-313735757
        - https://gist.github.com/wassname/0fb8f95e4272e6bdd27bd7df386716b7/
        
        Usage:
            import torchvision.models as models
            model = models.alexnet()
            df = torch_summarize_df(input_size=(3, 224,224), model=model)
            print(df)
            
            #              name class_name        input_shape       output_shape  nb_params
            # 1     features=>0     Conv2d  (-1, 3, 224, 224)   (-1, 64, 55, 55)      23296#(3*11*11+1)*64
            # 2     features=>1       ReLU   (-1, 64, 55, 55)   (-1, 64, 55, 55)          0
            # ...
        """

        def register_hook(module):
            def hook(module, input, output):
                name = ''
                for key, item in names.items():
                    if item == module:
                        name = key
                #<class 'torch.nn.modules.conv.Conv2d'>
                class_name = str(module.__class__).split('.')[-1].split("'")[0]
                module_idx = len(summary)

                m_key = module_idx + 1

                summary[m_key] = OrderedDict()
                summary[m_key]['name'] = name
                summary[m_key]['class_name'] = class_name
                if input_shape:
                    summary[m_key][
                        'input_shape'] = (-1, ) + tuple(input[0].size())[1:]
                summary[m_key]['output_shape'] = (-1, ) + tuple(output.size())[1:]
                if weights:
                    summary[m_key]['weights'] = list(
                        [tuple(p.size()) for p in module.parameters()])

                # summary[m_key]['trainable'] = any([p.requires_grad for p in module.parameters()])
                if nb_trainable:
                    params_trainable = sum([torch.LongTensor(list(p.size())).prod() for p in module.parameters() if p.requires_grad])
                    summary[m_key]['nb_trainable'] = params_trainable
                params = sum([torch.LongTensor(list(p.size())).prod() for p in module.parameters()])

                summary[m_key]['nb_params'] = params if isinstance(params, int) else params.item()
                

            if  not isinstance(module, nn.Sequential) and \
                not isinstance(module, nn.ModuleList) and \
                not (module == model):
                hooks.append(module.register_forward_hook(hook))
                
        # Names are stored in parent and path+name is unique not the name
        names = get_names_dict(model)

        # check if there are multiple inputs to the network
        if isinstance(input_size[0], (list, tuple)):
            x = [Variable(torch.rand(1, *in_size)) for in_size in input_size]
        else:
            x = Variable(torch.rand(1, *input_size))

        if next(model.parameters()).is_cuda:
            x = x.cuda()

        # create properties
        summary = OrderedDict()
        hooks = []

        # register hook
        model.apply(register_hook)

        # make a forward pass
        model(x)

        # remove these hooks
        for h in hooks:
            h.remove()

        # make dataframe
        df_summary = pd.DataFrame.from_dict(summary, orient='index')

        return df_summary

    return torch_summarize_df(input_size=input_size, model=model)

def print_model_parm_nums(model):
    total = sum([param.nelement() for param in model.parameters()])
    print('Number of Model Params: %.2fM' % (total / 1e6))
    
def print_model_parm_flops(model, input_size=(3,224,224)):

    prods = {}
    def save_hook(name):
        def hook_per(self, input, output):
            prods[name] = np.prod(input[0].shape)
        return hook_per

    list_1=[]
    def simple_hook(self, input, output):
        list_1.append(np.prod(input[0].shape))
    list_2={}
    def simple_hook2(self, input, output):
        list_2['names'] = np.prod(input[0].shape)


    multiply_adds = False
    list_conv=[]
    def conv_hook(self, input, output):
        batch_size, input_channels, input_height, input_width = input[0].size()
        output_channels, output_height, output_width = output[0].size()

        kernel_ops = self.kernel_size[0] * self.kernel_size[1] * (self.in_channels / self.groups) * (2 if multiply_adds else 1)
        bias_ops = 1 if self.bias is not None else 0

        params = output_channels * (kernel_ops + bias_ops)
        flops = batch_size * params * output_height * output_width

        list_conv.append(flops)


    list_linear=[] 
    def linear_hook(self, input, output):
        batch_size = input[0].size(0) if input[0].dim() == 2 else 1

        weight_ops = self.weight.nelement() * (2 if multiply_adds else 1)
        bias_ops = self.bias.nelement()

        flops = batch_size * (weight_ops + bias_ops)
        list_linear.append(flops)

    list_bn=[] 
    def bn_hook(self, input, output):
        list_bn.append(input[0].nelement())

    list_relu=[] 
    def relu_hook(self, input, output):
        list_relu.append(input[0].nelement())

    list_pooling=[]
    def pooling_hook(self, input, output):
        batch_size, input_channels, input_height, input_width = input[0].size()
        output_channels, output_height, output_width = output[0].size()

        kernel_ops = self.kernel_size * self.kernel_size
        bias_ops = 0
        params = output_channels * (kernel_ops + bias_ops)
        flops = batch_size * params * output_height * output_width

        list_pooling.append(flops)

    def foo(net):
        childrens = list(net.children())
        if not childrens:
            if isinstance(net, torch.nn.Conv2d):
                net.register_forward_hook(conv_hook)
            if isinstance(net, torch.nn.Linear):
                net.register_forward_hook(linear_hook)
            if isinstance(net, torch.nn.BatchNorm2d):
                net.register_forward_hook(bn_hook)
            if isinstance(net, torch.nn.ReLU):
                net.register_forward_hook(relu_hook)
            if isinstance(net, torch.nn.MaxPool2d) or isinstance(net, torch.nn.AvgPool2d):
                net.register_forward_hook(pooling_hook)
            return
        for c in childrens:
                foo(c)

    foo(model)
    inputs = Variable(torch.rand(input_size).unsqueeze(0), requires_grad = True)
    out = model(inputs)

    total_flops = (sum(list_conv) + sum(list_linear) + sum(list_bn) + sum(list_relu) + sum(list_pooling))
    print('Number of Model FLOPs: %.2fG' % (total_flops / 1e9))


